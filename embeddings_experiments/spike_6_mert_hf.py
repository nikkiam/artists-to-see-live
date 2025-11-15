#!/usr/bin/env python3
"""
Spike 6: MERT with HuggingFace Custom Endpoint (All 13 Layers)

Tests MERT-v1-95M with FULL 30-second context using custom Docker endpoint.
Extracts ALL 13 layers and tests each layer's similarity performance.

Goal: Determine optimal layer for artist similarity + whether chunking was the problem.
"""
import json
import os
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Optional

import librosa
import numpy as np
import requests
from sklearn.metrics.pairwise import cosine_similarity

# Load .env file if it exists
env_file = Path(__file__).parent / ".env"
if env_file.exists():
    with open(env_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                os.environ[key.strip()] = value.strip()

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from spike import (
    log,
    load_spotify_client,
    load_artist_id_mapping,
    load_music_map_data,
    get_artist_top_tracks_spotify,
    search_youtube_for_track,
    download_youtube_audio,
)


@dataclass(frozen=True)
class MultiLayerTrackEmbedding:
    """Track embedding with all 13 MERT layers preserved."""
    track_name: str
    artist_name: str
    spotify_id: str
    all_layers: list[list[float]]  # Shape: [13, 768]
    computed_at: str
    model: str = "mert-v1-95m-hf-13layers"


@dataclass(frozen=True)
class LayerSimilarityStats:
    """Similarity stats for a specific layer."""
    layer: int
    artist1: str
    artist2: str
    min_similarity: float
    mean_similarity: float
    max_similarity: float
    num_comparisons: int


def call_custom_endpoint(
    audio_path: Path,
    endpoint_url: str,
    hf_token: str
) -> Optional[np.ndarray]:
    """
    Call our custom MERT endpoint /embed.

    Returns [13, 768] embedding - all layers, time-reduced.
    """
    try:
        # Load full 30-second clip at 24kHz (MERT's native rate)
        audio, sr = librosa.load(audio_path, sr=24000, duration=30.0, mono=True)

        log(f"      Audio loaded: {len(audio)/sr:.1f}s at {sr}Hz")

        # Call our custom /embed endpoint
        response = requests.post(
            f"{endpoint_url}/embed",
            json={
                "audio": audio.tolist(),
                "sampling_rate": int(sr)
            },
            headers={
                "Authorization": f"Bearer {hf_token}",
                "Content-Type": "application/json"
            },
            timeout=60  # 60 second timeout for cold start
        )

        if response.status_code != 200:
            log(f"      ⚠️  Endpoint returned {response.status_code}: {response.text}")
            return None

        result = response.json()
        embedding = np.array(result["embedding"])  # Shape: [13, 768]

        log(f"      ✓ Endpoint returned embedding: shape {embedding.shape}")

        return embedding

    except Exception as e:
        log(f"      ⚠️  Endpoint call failed: {e}")
        return None


def load_cached_embeddings(cache_file: Path) -> dict[str, list[MultiLayerTrackEmbedding]]:
    """Load previously computed embeddings from cache."""
    if not cache_file.exists():
        return {}

    try:
        with open(cache_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        cached = {}
        for artist, tracks in data.items():
            cached[artist] = [
                MultiLayerTrackEmbedding(**track) for track in tracks
            ]

        log(f"  ✓ Loaded cached embeddings for {len(cached)} artists")
        return cached
    except Exception as e:
        log(f"  ⚠️  Failed to load embedding cache: {e}")
        return {}


def save_embeddings_cache(tracks_db: dict[str, list[MultiLayerTrackEmbedding]], cache_file: Path):
    """Save embeddings to cache for reuse."""
    try:
        tracks_json = {
            artist: [asdict(track) for track in tracks]
            for artist, tracks in tracks_db.items()
        }
        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump(tracks_json, f, indent=2)
        log(f"  ✓ Saved embeddings cache: {cache_file}")
    except Exception as e:
        log(f"  ⚠️  Failed to save embedding cache: {e}")


def compute_track_embeddings_custom_endpoint(
    artist_name: str,
    cache_dir: Path,
    endpoint_url: str,
    hf_token: str,
    spotify_client,
    artist_id_mapping: dict[str, str] = None,
) -> list[MultiLayerTrackEmbedding]:
    """Extract MERT embeddings (all 13 layers) for individual tracks."""
    log(f"Processing artist: {artist_name}")

    spotify_tracks = get_artist_top_tracks_spotify(
        spotify_client, artist_name, limit=5, artist_id_mapping=artist_id_mapping
    )

    if not spotify_tracks:
        log(f"  ❌ No tracks found on Spotify for {artist_name}")
        return []

    log(f"  Found {len(spotify_tracks)} tracks on Spotify")

    track_embeddings = []

    from datetime import datetime
    timestamp = datetime.now().isoformat()

    for spotify_track in spotify_tracks:
        youtube_track = search_youtube_for_track(
            spotify_track.artist_name,
            spotify_track.name
        )

        if not youtube_track:
            log(f"    ⚠️  YouTube search failed for: {spotify_track.name}")
            continue

        audio_path = cache_dir / f"{youtube_track.video_id}.wav"

        # Download if not cached
        if not audio_path.exists():
            log(f"    Downloading: {spotify_track.name}")
            if not download_youtube_audio(youtube_track.video_id, audio_path):
                continue
        else:
            log(f"    Using cached: {spotify_track.name}")

        # Extract embedding via custom endpoint (all 13 layers)
        emb = call_custom_endpoint(audio_path, endpoint_url, hf_token)

        if emb is not None and emb.shape == (13, 768):
            track_embeddings.append(
                MultiLayerTrackEmbedding(
                    track_name=spotify_track.name,
                    artist_name=artist_name,
                    spotify_id=spotify_track.spotify_id,
                    all_layers=emb.tolist(),
                    computed_at=timestamp,
                )
            )
            log(f"    ✓ Extracted 13-layer MERT embedding: {spotify_track.name}")
        else:
            log(f"    ❌ Invalid embedding shape for: {spotify_track.name}")

    log(f"  ✓ Extracted {len(track_embeddings)} track embeddings")

    return track_embeddings


def compute_layer_similarities(
    tracks_db: dict[str, list[MultiLayerTrackEmbedding]],
    layer_idx: int
) -> list[LayerSimilarityStats]:
    """
    Compute track-level similarities for a specific layer.

    Extracts layer_idx from all tracks, then computes all pairwise similarities.
    """
    artists = list(tracks_db.keys())
    similarities = []

    for i, artist1 in enumerate(artists):
        for artist2 in artists[i + 1:]:
            tracks1 = tracks_db[artist1]
            tracks2 = tracks_db[artist2]

            # Extract layer_idx from all tracks
            track_sims = []

            for track1 in tracks1:
                emb1 = np.array(track1.all_layers[layer_idx]).reshape(1, -1)  # [1, 768]
                for track2 in tracks2:
                    emb2 = np.array(track2.all_layers[layer_idx]).reshape(1, -1)
                    sim = float(cosine_similarity(emb1, emb2)[0, 0])
                    track_sims.append(sim)

            # Compute statistics
            min_sim = float(np.min(track_sims))
            mean_sim = float(np.mean(track_sims))
            max_sim = float(np.max(track_sims))

            similarities.append(LayerSimilarityStats(
                layer=layer_idx,
                artist1=artist1,
                artist2=artist2,
                min_similarity=min_sim,
                mean_similarity=mean_sim,
                max_similarity=max_sim,
                num_comparisons=len(track_sims)
            ))

    return similarities


def run_spike_6(test_one_artist: bool = False) -> None:
    """Run Spike 6 with custom HuggingFace endpoint."""

    log("=" * 80)
    log("SPIKE 6: MERT WITH CUSTOM ENDPOINT (ALL 13 LAYERS)")
    log("=" * 80)
    log("")
    log("Testing MERT-v1-95M with:")
    log("  - FULL 30-second context (no chunking)")
    log("  - ALL 13 layers preserved (choose empirically)")
    log("  - Custom Docker endpoint with GPU inference")

    if test_one_artist:
        log("TEST MODE: Processing 1 artist only (deadmau5)")

    log("")

    try:
        # Setup paths
        project_root = Path(__file__).parent.parent
        music_map_path = project_root / "output" / "similar_artists_map.json"
        cache_dir = Path(__file__).parent / "data" / "audio_cache"
        cache_dir.mkdir(parents=True, exist_ok=True)

        all_artists = [
            "deadmau5",
            "Rezz",
            "TroyBoi",
            "IMANU",
            "PEEKABOO",
            "Sabrina Carpenter",
            "Vril",
            "Calibre",
        ]

        test_artists = ["deadmau5"] if test_one_artist else all_artists

        log("[1/6] Loading music-map data...")
        music_map_data = load_music_map_data(music_map_path)
        log(f"  Loaded {len(music_map_data)} artists")
        log(f"  Testing with {len(test_artists)} artists: {test_artists}")

        log("")
        log("[2/6] Initializing Spotify...")
        spotify_client = load_spotify_client()
        artist_id_mapping = load_artist_id_mapping()
        log("  ✓ Spotify ready")

        log("")
        log("[3/6] Initializing Custom HuggingFace Endpoint...")

        hf_token = os.environ.get("HF_TOKEN")
        hf_endpoint_url = os.environ.get("HF_ENDPOINT_URL")

        if not hf_token:
            log("  ❌ ERROR: HF_TOKEN not set!")
            return

        if not hf_endpoint_url:
            log("  ❌ ERROR: HF_ENDPOINT_URL not set!")
            log("  Please deploy the Docker container and set the endpoint URL.")
            return

        # Test endpoint health
        try:
            health_response = requests.get(f"{hf_endpoint_url}/health", timeout=10)
            if health_response.status_code == 200:
                log(f"  ✓ Endpoint healthy: {hf_endpoint_url}")
            else:
                log(f"  ⚠️  Endpoint returned {health_response.status_code}")
        except Exception as e:
            log(f"  ⚠️  Could not reach endpoint: {e}")
            return

        log("")
        log("[4/6] Extracting track-level embeddings (13 layers)...")

        # Load embedding cache
        embedding_cache_file = Path(__file__).parent / "data" / "spike_6_embedding_cache.json"
        tracks_db = load_cached_embeddings(embedding_cache_file)

        log(f"  Audio cache: {cache_dir}")
        log(f"  Cached audio files: {len(list(cache_dir.glob('*.wav')))} WAV files")
        log(f"  Cached embeddings: {len(tracks_db)} artists")
        log("")

        # Process artists not in cache
        artists_to_process = [a for a in test_artists if a not in tracks_db]

        if artists_to_process:
            log(f"  Processing {len(artists_to_process)} artists: {artists_to_process}")
            log(f"  (Skipping {len(test_artists) - len(artists_to_process)} cached artists)")
            log("")

            for artist in artists_to_process:
                track_embs = compute_track_embeddings_custom_endpoint(
                    artist, cache_dir, hf_endpoint_url, hf_token,
                    spotify_client, artist_id_mapping
                )
                if track_embs:
                    tracks_db[artist] = track_embs
                    # Save cache after each artist (safety!)
                    save_embeddings_cache(tracks_db, embedding_cache_file)
                log("")
        else:
            log(f"  ✓ All {len(test_artists)} artists already cached!")
            log("")

        log(f"  ✓ Total artists with embeddings: {len(tracks_db)}/{len(test_artists)}")

        # Count total tracks
        total_tracks = sum(len(tracks) for tracks in tracks_db.values())
        log(f"  ✓ Total tracks with embeddings: {total_tracks}")

        if len(tracks_db) < 2:
            log("")
            log("❌ FATAL ERROR: Not enough artists to compute similarities")
            return

        log("")
        log("[5/6] Computing layer-wise similarities (13 layers × all combinations)...")

        # Compute similarities for each layer
        all_layer_results = {}

        for layer_idx in range(13):
            log(f"\n  Computing Layer {layer_idx + 1}/13...")
            layer_sims = compute_layer_similarities(tracks_db, layer_idx)
            all_layer_results[f"layer_{layer_idx}"] = layer_sims

            # Print stats for this layer
            all_means = [s.mean_similarity for s in layer_sims]
            log(f"    Mean range: {min(all_means):.3f} - {max(all_means):.3f} (span: {max(all_means) - min(all_means):.3f})")

        log("")
        log("[6/6] Saving results...")

        output_dir = Path(__file__).parent / "data"

        # Save track-level embeddings
        tracks_json = {
            artist: [asdict(track) for track in tracks]
            for artist, tracks in tracks_db.items()
        }
        with open(output_dir / "spike_6_track_embeddings.json", "w", encoding="utf-8") as f:
            json.dump(tracks_json, f, indent=2)

        # Save layer-wise similarity results
        layer_results_json = {
            layer_key: [asdict(s) for s in sims]
            for layer_key, sims in all_layer_results.items()
        }
        with open(output_dir / "spike_6_layer_similarities.json", "w", encoding="utf-8") as f:
            json.dump(layer_results_json, f, indent=2)

        log("  ✓ Results saved")

        # Print summary
        log("")
        log("=" * 80)
        log("SPIKE 6 SUMMARY (Per-Layer Analysis)")
        log("=" * 80)

        # Find best and worst layers
        layer_stats = []
        for layer_idx in range(13):
            layer_sims = all_layer_results[f"layer_{layer_idx}"]
            all_means = [s.mean_similarity for s in layer_sims]
            span = max(all_means) - min(all_means)
            layer_stats.append((layer_idx, span, min(all_means), max(all_means)))

        # Sort by span (widest = best discrimination)
        layer_stats_sorted = sorted(layer_stats, key=lambda x: x[1], reverse=True)

        log("\nLayer Performance (by similarity range span):")
        for layer_idx, span, min_val, max_val in layer_stats_sorted:
            log(f"  Layer {layer_idx:2d}: {min_val:.3f} - {max_val:.3f} (span: {span:.3f})")

        best_layer, best_span, _, _ = layer_stats_sorted[0]
        worst_layer, worst_span, _, _ = layer_stats_sorted[-1]

        log("")
        log(f"Best Layer: {best_layer} (span: {best_span:.3f})")
        log(f"Worst Layer: {worst_layer} (span: {worst_span:.3f})")

        log("")
        log("=" * 80)
        log("COMPARISON TO SPIKE 5")
        log("=" * 80)
        log("Spike 5 (Layer 13, 10s chunks): 0.808 - 0.971 (span: 0.163)")
        log(f"Spike 6 (Best layer, 30s full):  {layer_stats_sorted[0][2]:.3f} - {layer_stats_sorted[0][3]:.3f} (span: {best_span:.3f})")

        if best_span > 0.25:
            log("\n✓ IMPROVEMENT: Wider range - layer selection and/or full context helps!")
        else:
            log("\n❌ NO IMPROVEMENT: Range still narrow even with optimal layer + full context")

        log("")
        log("=" * 80)
        log("SPIKE 6 COMPLETE")
        log("=" * 80)

    except Exception as e:
        log("")
        log(f"❌ FATAL ERROR: {str(e)}")
        import traceback
        log(traceback.format_exc())
        raise


if __name__ == "__main__":
    import sys

    os.environ["TF_CPP_MIN_LOG_LEVEL"] = "2"

    test_mode = "--test" in sys.argv or "-t" in sys.argv

    if test_mode:
        print("Running in TEST MODE: Processing 1 artist only")

    run_spike_6(test_one_artist=test_mode)
