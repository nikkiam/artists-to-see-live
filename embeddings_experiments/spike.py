#!/usr/bin/env python3
"""
Embeddings Spike - Validate VGGish embeddings vs music-map.com similarity.

This script:
1. Selects test artists from music-map.com data
2. Extracts VGGish embeddings from Spotify track previews
3. Computes artist similarity via cosine distance
4. Validates against music-map.com ground truth

All output goes to log file per CLAUDE.md standards.
"""

import json
import os
import random
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

import subprocess

import librosa
import numpy as np
import requests
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
import tensorflow as tf
import tensorflow_hub as hub
from scipy.stats import pearsonr
from sklearn.metrics.pairwise import cosine_similarity
import yt_dlp

# --- Logging Setup (Per CLAUDE.md) ---

LOG_FILE = (
    Path(__file__).parent / "logs" / f"spike_{datetime.now().strftime('%Y-%m-%d')}.log"
)


def log(message: str) -> None:
    """Log to file only - NO PRINT STATEMENTS"""
    LOG_FILE.parent.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] {message}\n")


# --- Data Models (Typed Dataclasses) ---


@dataclass(frozen=True)
class TrackInfo:
    name: str
    video_id: str
    url: str


@dataclass(frozen=True)
class SpotifyTrack:
    name: str
    artist_name: str
    spotify_id: str
    preview_url: Optional[str]


@dataclass(frozen=True)
class ArtistEmbedding:
    artist_name: str
    embedding: list[float]  # Serializable for JSON
    tracks_used: list[str]
    spotify_ids: list[str]
    computed_at: str
    model: str = "vggish"


@dataclass(frozen=True)
class SimilarityResult:
    artist1: str
    artist2: str
    cosine_similarity: float


@dataclass(frozen=True)
class MusicMapData:
    artist_name: str
    similar_artists: list[str]  # Just names, ranked by similarity


# --- Spotify Integration ---


def load_spotify_client() -> spotipy.Spotify:
    """Initialize Spotify client using existing credentials.

    Tries to load from spotify-config.json in root or src directory.
    """
    # Try root directory first, then src directory
    root_config = Path(__file__).parent.parent / "spotify-config.json"
    src_config = Path(__file__).parent.parent / "src" / "spotify-config.json"

    config_path = root_config if root_config.exists() else src_config

    if not config_path.exists():
        raise FileNotFoundError(
            "spotify-config.json not found in root or src directory. "
            "Please create it with clientId and clientSecret fields."
        )

    with open(config_path, encoding="utf-8") as f:
        config = json.load(f)

    auth_manager = SpotifyClientCredentials(
        client_id=config["clientId"],
        client_secret=config["clientSecret"]
    )

    return spotipy.Spotify(auth_manager=auth_manager)


def load_artist_id_mapping() -> dict[str, str]:
    """Load manual artist ID mapping for ambiguous artist names."""
    mapping_path = Path(__file__).parent / "artist_id_mapping.json"

    if not mapping_path.exists():
        return {}

    with open(mapping_path, encoding="utf-8") as f:
        data = json.load(f)
        return data.get("mapping", {})


def get_artist_top_tracks_spotify(
    spotify: spotipy.Spotify,
    artist_name: str,
    limit: int = 5,
    artist_id_mapping: dict[str, str] = None
) -> list[SpotifyTrack]:
    """Get artist's top tracks from Spotify for precise YouTube search.

    Uses artist ID mapping if provided to avoid name ambiguity.

    Early exit pattern:
    - Return empty list if artist not found
    - Return empty list if no tracks available
    """
    log(f"  Searching Spotify for artist: {artist_name}")

    try:
        # Check if we have a manual ID mapping for this artist
        if artist_id_mapping and artist_name in artist_id_mapping:
            artist_id = artist_id_mapping[artist_name]
            log(f"    ✓ Using mapped artist ID: {artist_id}")

            # Get artist details
            artist = spotify.artist(artist_id)
            actual_name = artist['name']
            log(f"    ✓ Found artist on Spotify: {actual_name} (ID: {artist_id})")
        else:
            # Search for artist by name
            results = spotify.search(q=f'artist:"{artist_name}"', type='artist', limit=1)

            if not results['artists']['items']:
                log(f"    ⚠️  Artist not found on Spotify: {artist_name}")
                return []

            artist = results['artists']['items'][0]
            artist_id = artist['id']
            actual_name = artist['name']

            log(f"    ✓ Found artist on Spotify: {actual_name} (ID: {artist_id})")

        # Get top tracks (by popularity)
        top_tracks = spotify.artist_top_tracks(artist_id, country='US')

        tracks = []
        for track in top_tracks['tracks'][:limit]:
            tracks.append(SpotifyTrack(
                name=track['name'],
                artist_name=actual_name,
                spotify_id=track['id'],
                preview_url=track.get('preview_url')
            ))

        log(f"    ✓ Retrieved {len(tracks)} top tracks from Spotify")
        return tracks

    except Exception as e:
        log(f"    ⚠️  Spotify lookup failed: {e}")
        return []


# --- YouTube Audio Functions ---


def search_youtube_tracks(artist_name: str, limit: int = 5) -> list[TrackInfo]:
    """Search YouTube for artist tracks, return track info."""
    try:
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': True,
            'default_search': 'ytsearch',
        }

        # Search for "artist name topic" to get official uploads
        search_query = f"ytsearch{limit}:{artist_name} topic"

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            result = ydl.extract_info(search_query, download=False)

            if not result or 'entries' not in result:
                return []

            tracks = []
            for entry in result['entries']:
                if entry:
                    tracks.append(
                        TrackInfo(
                            name=entry.get('title', 'Unknown'),
                            video_id=entry.get('id', ''),
                            url=entry.get('url', ''),
                        )
                    )
            return tracks

    except Exception as e:
        log(f"    ⚠️  YouTube search failed: {e}")
        return []


def search_youtube_for_track(
    artist_name: str,
    track_name: str,
    max_results: int = 3
) -> Optional[TrackInfo]:
    """Search YouTube for a specific track using exact artist + track name.

    Returns the best match (first result from exact search).
    """
    try:
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': True,
            'default_search': 'ytsearch',
        }

        # Try exact match with quotes first
        search_query = f'ytsearch{max_results}:"{artist_name} - {track_name}"'

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            result = ydl.extract_info(search_query, download=False)

            if not result or 'entries' not in result or not result['entries']:
                # Fallback: try without quotes
                log(f"      Fallback: searching without quotes")
                search_query = f'ytsearch{max_results}:{artist_name} - {track_name}'
                result = ydl.extract_info(search_query, download=False)

            if not result or 'entries' not in result:
                return None

            # Pick first result
            for entry in result['entries']:
                if entry:
                    return TrackInfo(
                        name=f"{artist_name} - {track_name}",
                        video_id=entry.get('id', ''),
                        url=entry.get('url', ''),
                    )

            return None

    except Exception as e:
        log(f"      ⚠️  YouTube search failed for '{artist_name} - {track_name}': {e}")
        return None


def download_youtube_audio(video_id: str, output_path: Path) -> bool:
    """Download audio from YouTube video using yt-dlp."""
    try:
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': str(output_path.with_suffix('')),  # Remove extension, yt-dlp adds it
            'quiet': True,
            'no_warnings': True,
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'wav',  # VGGish needs raw audio
            }],
        }

        url = f"https://www.youtube.com/watch?v={video_id}"

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        # yt-dlp adds .wav extension
        actual_path = output_path.with_suffix('.wav')
        if actual_path.exists():
            return True
        return False

    except Exception as e:
        log(f"      ⚠️  Download failed: {e}")
        return False


# --- VGGish Embedding Functions ---


def load_vggish_model() -> hub.KerasLayer:
    """Load VGGish model from TensorFlow Hub."""
    log("  Loading VGGish model from TensorFlow Hub...")
    model_url = "https://tfhub.dev/google/vggish/1"
    model = hub.KerasLayer(model_url)
    log("  ✓ VGGish model loaded")
    return model


def extract_vggish_embedding(audio_path: Path, model: hub.KerasLayer) -> Optional[np.ndarray]:
    """Extract VGGish embedding from audio file.

    VGGish expects:
    - 16kHz mono audio as 1D tensor
    - Returns 128-dim embedding per frame
    """
    try:
        # Load audio at 16kHz (VGGish requirement)
        audio, sr = librosa.load(audio_path, sr=16000, mono=True)

        # VGGish expects 1D audio waveform (no batch dimension)
        audio_tensor = tf.constant(audio, dtype=tf.float32)

        # Extract embedding - returns (num_frames, 128)
        embedding = model(audio_tensor)

        # Average over time frames to get single 128-dim vector
        embedding_avg = tf.reduce_mean(embedding, axis=0)

        return embedding_avg.numpy()
    except Exception as e:
        log(f"      ⚠️  Embedding extraction failed: {e}")
        return None


def compute_artist_embedding(
    artist_name: str, cache_dir: Path, vggish_model: hub.KerasLayer
) -> Optional[ArtistEmbedding]:
    """
    Compute artist-level embedding by averaging track embeddings from YouTube.

    Early exit pattern:
    - Return None if no tracks found on YouTube
    - Return None if no successful downloads
    - Return None if embedding extraction fails
    """
    log(f"Processing artist: {artist_name}")

    # Early exit: Search YouTube for tracks
    tracks = search_youtube_tracks(artist_name, limit=5)
    if not tracks:
        log(f"  ❌ No tracks found on YouTube for {artist_name}")
        return None

    log(f"  Found {len(tracks)} tracks on YouTube")

    # Extract embeddings for each track
    embeddings = []
    track_names = []
    track_ids = []

    for track in tracks:
        audio_path = cache_dir / f"{track.video_id}.wav"

        # Download if not cached
        if not audio_path.exists():
            if not download_youtube_audio(track.video_id, audio_path):
                continue

        # Extract embedding
        emb = extract_vggish_embedding(audio_path, vggish_model)
        if emb is not None:
            embeddings.append(emb)
            track_names.append(track.name)
            track_ids.append(track.video_id)
            log(f"    ✓ Extracted embedding for: {track.name}")

    # Early exit: Need at least one successful embedding
    if not embeddings:
        log(f"  ❌ No successful embeddings for {artist_name}")
        return None

    # Average embeddings to get artist-level representation
    avg_embedding = np.mean(embeddings, axis=0)

    log(f"  ✓ Computed artist embedding from {len(embeddings)} tracks")

    return ArtistEmbedding(
        artist_name=artist_name,
        embedding=avg_embedding.tolist(),  # Convert to list for JSON serialization
        tracks_used=track_names,
        spotify_ids=track_ids,  # Now contains YouTube video IDs
        computed_at=datetime.now().isoformat(),
        model="vggish",
    )


def compute_artist_embedding_v2(
    artist_name: str,
    cache_dir: Path,
    vggish_model: hub.KerasLayer,
    spotify_client: spotipy.Spotify,
    artist_id_mapping: dict[str, str] = None
) -> Optional[ArtistEmbedding]:
    """
    Compute artist-level embedding using Spotify-guided YouTube search.

    Process:
    1. Get top tracks from Spotify (using ID mapping if provided)
    2. Search YouTube for each track using exact artist+track query
    3. Download and extract embeddings
    4. Average embeddings for artist-level representation
    """
    log(f"Processing artist: {artist_name}")

    # Get tracks from Spotify
    spotify_tracks = get_artist_top_tracks_spotify(
        spotify_client, artist_name, limit=5, artist_id_mapping=artist_id_mapping
    )

    if not spotify_tracks:
        log(f"  ❌ No tracks found on Spotify for {artist_name}")
        return None

    log(f"  Found {len(spotify_tracks)} tracks on Spotify")

    # Search YouTube and extract embeddings
    embeddings = []
    track_names = []
    track_ids = []

    for spotify_track in spotify_tracks:
        # Search YouTube for this specific track
        youtube_track = search_youtube_for_track(
            spotify_track.artist_name,  # Use Spotify's canonical name
            spotify_track.name
        )

        if not youtube_track:
            log(f"    ⚠️  YouTube search failed for: {spotify_track.name}")
            continue

        audio_path = cache_dir / f"{youtube_track.video_id}.wav"

        # Download if not cached
        if not audio_path.exists():
            if not download_youtube_audio(youtube_track.video_id, audio_path):
                continue

        # Extract embedding
        emb = extract_vggish_embedding(audio_path, vggish_model)
        if emb is not None:
            embeddings.append(emb)
            track_names.append(spotify_track.name)  # Store Spotify track name
            track_ids.append(spotify_track.spotify_id)  # Store Spotify ID
            log(f"    ✓ Extracted embedding for: {spotify_track.name}")

    # Early exit: Need at least one successful embedding
    if not embeddings:
        log(f"  ❌ No successful embeddings for {artist_name}")
        return None

    # Average embeddings
    avg_embedding = np.mean(embeddings, axis=0)

    log(f"  ✓ Computed artist embedding from {len(embeddings)} tracks")

    return ArtistEmbedding(
        artist_name=artist_name,
        embedding=avg_embedding.tolist(),
        tracks_used=track_names,
        spotify_ids=track_ids,
        computed_at=datetime.now().isoformat(),
        model="vggish-spotify-guided",
    )


# --- Music-Map Data Loading ---


def load_music_map_data(filepath: Path) -> dict[str, MusicMapData]:
    """Load similar artists from music-map.com data.

    Filter to only successful entries with similar_artists data.
    """
    with open(filepath, encoding="utf-8") as f:
        raw_data = json.load(f)

    music_map = {}
    for artist_name, data in raw_data.items():
        if data.get("status") == "success" and "similar_artists" in data:
            similar_artists = [sa["name"] for sa in data["similar_artists"]]
            music_map[artist_name] = MusicMapData(
                artist_name=artist_name, similar_artists=similar_artists
            )

    return music_map


# --- Validation Functions ---


def compute_pairwise_similarities(
    embeddings_db: dict[str, ArtistEmbedding]
) -> list[SimilarityResult]:
    """Compute cosine similarity between all pairs of artists."""
    log("\n=== Computing Pairwise Similarities ===")

    artists = list(embeddings_db.keys())
    similarities = []

    for i, artist1 in enumerate(artists):
        for artist2 in artists[i + 1 :]:
            emb1 = np.array(embeddings_db[artist1].embedding).reshape(1, -1)
            emb2 = np.array(embeddings_db[artist2].embedding).reshape(1, -1)

            sim = float(cosine_similarity(emb1, emb2)[0, 0])
            similarities.append(
                SimilarityResult(artist1=artist1, artist2=artist2, cosine_similarity=sim)
            )
            log(f"  {artist1} <-> {artist2}: {sim:.3f}")

    return similarities


def validate_vs_music_map(
    embeddings_db: dict[str, ArtistEmbedding],
    music_map_data: dict[str, MusicMapData],
    similarities: list[SimilarityResult],
) -> dict:
    """
    Validate embedding-based similarity against music-map.com.

    Returns metrics:
    - top5_overlap_avg: Average overlap of top-5 similar artists
    - per_artist_results: Detailed results per artist
    """
    log("\n=== Validation: Embeddings vs Music-Map ===")

    per_artist_results = {}

    for artist_name, artist_emb in embeddings_db.items():
        # Skip if not in music-map
        if artist_name not in music_map_data:
            log(f"  ⚠️  {artist_name} not in music-map data, skipping validation")
            continue

        # Get music-map top similar artists
        music_map_top = music_map_data[artist_name].similar_artists[:5]

        # Get embedding-based top similar artists
        artist_sims = [
            s
            for s in similarities
            if s.artist1 == artist_name or s.artist2 == artist_name
        ]
        artist_sims_sorted = sorted(
            artist_sims, key=lambda x: x.cosine_similarity, reverse=True
        )

        embedding_top = []
        for sim in artist_sims_sorted[:5]:
            other_artist = sim.artist2 if sim.artist1 == artist_name else sim.artist1
            embedding_top.append(other_artist)

        # Compute overlap
        overlap = len(set(music_map_top) & set(embedding_top))
        overlap_pct = overlap / 5.0 if music_map_top else 0.0

        per_artist_results[artist_name] = {
            "music_map_top5": music_map_top,
            "embedding_top5": embedding_top,
            "overlap": overlap,
            "overlap_pct": overlap_pct,
        }

        log(
            f"  {artist_name}: {overlap}/5 overlap ({overlap_pct * 100:.0f}%)"
        )

    # Compute average overlap
    overlaps = [r["overlap_pct"] for r in per_artist_results.values()]
    top5_overlap_avg = np.mean(overlaps) if overlaps else 0.0

    log(f"\n  📊 Average Top-5 Overlap: {top5_overlap_avg * 100:.1f}%")

    return {
        "metrics": {"top5_overlap_avg": top5_overlap_avg},
        "per_artist_results": per_artist_results,
    }


# --- Main Execution ---


def run_spike(custom_artists: Optional[list[str]] = None) -> None:
    """Main spike execution - all logging to file.

    Args:
        custom_artists: Optional list of specific artists to test. If None, uses random selection.
    """
    log("=" * 80)
    log("EMBEDDINGS SPIKE - START")
    log("=" * 80)

    try:
        # Setup paths
        project_root = Path(__file__).parent.parent
        music_map_path = project_root / "output" / "similar_artists_map.json"
        cache_dir = Path(__file__).parent / "data" / "audio_cache"
        cache_dir.mkdir(parents=True, exist_ok=True)

        # 1. Load music-map data and select test artists
        log("\n[1/4] Loading music-map data and selecting test artists...")
        music_map_data = load_music_map_data(music_map_path)
        log(f"  Loaded {len(music_map_data)} artists from music-map.com")

        if custom_artists:
            # Use provided artist list
            test_artists = custom_artists
            log(f"  Using custom artist list: {test_artists}")
        else:
            # Select test artists (try more to ensure we get 10 with previews)
            all_artists = list(music_map_data.keys())
            random.seed(42)  # Reproducible selection
            candidate_artists = random.sample(all_artists, min(30, len(all_artists)))
            log(f"  Selected {len(candidate_artists)} candidate artists to test for preview availability")

            # We'll filter to artists with previews during extraction
            test_artists = candidate_artists

        # 2. Initialize Spotify client
        log("\n[2/5] Initializing Spotify client...")
        spotify_client = load_spotify_client()
        log("  ✓ Spotify client initialized")

        # Load artist ID mapping for ambiguous names
        artist_id_mapping = load_artist_id_mapping()
        if artist_id_mapping:
            log(f"  ✓ Loaded artist ID mapping for {len(artist_id_mapping)} artists")

        # 3. Load VGGish model
        log("\n[3/5] Loading VGGish model...")
        vggish_model = load_vggish_model()

        # 4. Extract embeddings using Spotify-guided YouTube search
        log("\n[4/5] Extracting embeddings (Spotify-guided YouTube search with ID mapping)...")
        embeddings_db = {}

        # Determine target count
        target_count = len(test_artists) if custom_artists else 10

        for artist in test_artists:
            # Stop once we reach target (all custom artists, or 10 if random)
            if not custom_artists and len(embeddings_db) >= 10:
                log(f"  ✓ Reached target of 10 artists with embeddings, stopping")
                break

            emb = compute_artist_embedding_v2(
                artist, cache_dir, vggish_model, spotify_client, artist_id_mapping
            )
            if emb:
                embeddings_db[artist] = emb

        log(
            f"\n  ✓ Successfully extracted embeddings for {len(embeddings_db)}/{len(test_artists)} artists"
        )
        extraction_rate = len(embeddings_db) / len(test_artists)
        log(f"  📊 Extraction success rate: {extraction_rate * 100:.1f}%")

        # 5. Compute similarities and validate
        log("\n[5/5] Computing similarities and validating...")
        similarities = compute_pairwise_similarities(embeddings_db)
        validation_results = validate_vs_music_map(
            embeddings_db, music_map_data, similarities
        )

        # Save results
        output_dir = Path(__file__).parent / "data"
        output_dir.mkdir(exist_ok=True)

        # Save embeddings
        embeddings_json = {
            name: asdict(emb) for name, emb in embeddings_db.items()
        }
        with open(output_dir / "spike_embeddings.json", "w", encoding="utf-8") as f:
            json.dump(embeddings_json, f, indent=2)

        # Save similarities
        similarities_json = [asdict(s) for s in similarities]
        with open(output_dir / "spike_similarities.json", "w", encoding="utf-8") as f:
            json.dump({"pairwise_similarities": similarities_json}, f, indent=2)

        # Save validation results
        with open(output_dir / "spike_validation.json", "w", encoding="utf-8") as f:
            json.dump(validation_results, f, indent=2)

        log("\n  ✓ Results saved to embeddings_experiments/data/")

        # Final summary
        log("\n" + "=" * 80)
        log("SPIKE SUMMARY")
        log("=" * 80)
        log(f"Extraction Rate: {extraction_rate * 100:.1f}%")
        log(
            f"Top-5 Overlap: {validation_results['metrics']['top5_overlap_avg'] * 100:.1f}%"
        )
        log("\n" + "=" * 80)
        log("EMBEDDINGS SPIKE - COMPLETE")
        log("=" * 80)

    except Exception as e:
        log(f"\n❌ FATAL ERROR: {str(e)}")
        import traceback

        log(traceback.format_exc())
        raise


if __name__ == "__main__":
    # Suppress TensorFlow warnings
    os.environ["TF_CPP_MIN_LOG_LEVEL"] = "2"
    tf.get_logger().setLevel("ERROR")

    # Check if custom artists are provided via environment variable or use default list
    import sys

    # Custom artist list for validation experiment
    custom_test_artists = [
        "deadmau5",
        "Rezz",
        "TroyBoi",
        "IMANU",
        "PEEKABOO",
        "Sabrina Carpenter",
        "Vril",
        "Calibre"
    ]

    # Run with custom artists if --custom flag is passed
    if len(sys.argv) > 1 and sys.argv[1] == "--custom":
        run_spike(custom_artists=custom_test_artists)
    else:
        run_spike()
