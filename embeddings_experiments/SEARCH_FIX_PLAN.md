# Fix Plan: YouTube Search Accuracy via Spotify-Guided Search

## Problem Statement

The current YouTube "topic" search (`ytsearch:artist topic`) returns incorrect tracks due to name ambiguity:
- **Vril** (techno) → Avril Lavigne (pop-punk)
- **PEEKABOO** (bass) → Kendrick Lamar's "peekaboo" song + K-pop
- **Calibre** (dnb) → Calibre 50 (Mexican banda)

This pollutes embeddings and makes all artists appear similar (0.83-0.96 cosine similarity).

## Proposed Solution

### Two-Stage Search Strategy

**Stage 1: Spotify API → Get Exact Track Names**
1. Search Spotify for artist by name
2. Get artist's top tracks (5-10 tracks)
3. Extract track names and Spotify IDs

**Stage 2: YouTube Search → Precise Matching**
1. Search YouTube with exact query: `"Artist Name - Track Name"`
2. Use quotes for exact matching
3. Prefer official uploads (check uploader name/verified status)
4. Fallback: search without quotes if no results

## Implementation Plan

### 1. Add Spotify Client Setup

```python
# Add to spike.py imports
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials

# New function to load Spotify config (reuse from extract_artists_from_spotify_playlists.py)
def load_spotify_client() -> spotipy.Spotify:
    """Initialize Spotify client using existing credentials."""
    config_path = Path(__file__).parent.parent / "src" / "spotify-config.json"
    with open(config_path, encoding="utf-8") as f:
        config = json.load(f)

    # Use client credentials flow
    auth_manager = SpotifyClientCredentials(
        client_id=config["clientId"],
        client_secret=config["clientSecret"]
    )
    return spotipy.Spotify(auth_manager=auth_manager)
```

### 2. Add Spotify Track Lookup Function

```python
@dataclass(frozen=True)
class SpotifyTrack:
    name: str
    artist_name: str
    spotify_id: str
    preview_url: Optional[str]  # For future: could use Spotify's 30s previews

def get_artist_top_tracks_spotify(
    spotify: spotipy.Spotify,
    artist_name: str,
    limit: int = 5
) -> list[SpotifyTrack]:
    """Get artist's top tracks from Spotify for precise YouTube search.

    Early exit pattern:
    - Return empty list if artist not found
    - Return empty list if no tracks available
    """
    log(f"  Searching Spotify for artist: {artist_name}")

    try:
        # Search for artist
        results = spotify.search(q=f'artist:"{artist_name}"', type='artist', limit=1)

        if not results['artists']['items']:
            log(f"    ⚠️  Artist not found on Spotify: {artist_name}")
            return []

        artist = results['artists']['items'][0]
        artist_id = artist['id']
        actual_name = artist['name']

        log(f"    ✓ Found artist on Spotify: {actual_name} (ID: {artist_id})")

        # Get top tracks (by popularity)
        # Note: top_tracks requires market parameter
        top_tracks = spotify.artist_top_tracks(artist_id, country='US')

        tracks = []
        for track in top_tracks['tracks'][:limit]:
            tracks.append(SpotifyTrack(
                name=track['name'],
                artist_name=actual_name,  # Use Spotify's canonical name
                spotify_id=track['id'],
                preview_url=track.get('preview_url')
            ))

        log(f"    ✓ Retrieved {len(tracks)} top tracks from Spotify")
        return tracks

    except Exception as e:
        log(f"    ⚠️  Spotify lookup failed: {e}")
        return []
```

### 3. Modify YouTube Search to Use Exact Queries

```python
def search_youtube_for_track(
    artist_name: str,
    track_name: str,
    max_results: int = 3
) -> Optional[TrackInfo]:
    """Search YouTube for a specific track using exact artist + track name.

    Returns the best match (prioritizing official/verified uploads).
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
                search_query = f'ytsearch{max_results}:{artist_name} - {track_name}'
                result = ydl.extract_info(search_query, download=False)

            if not result or 'entries' not in result:
                return None

            # Pick first result (could add logic to prefer verified channels)
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
```

### 4. Refactor `compute_artist_embedding` Function

```python
def compute_artist_embedding_v2(
    artist_name: str,
    cache_dir: Path,
    vggish_model: hub.KerasLayer,
    spotify_client: spotipy.Spotify
) -> Optional[ArtistEmbedding]:
    """
    Compute artist-level embedding using Spotify-guided YouTube search.

    Process:
    1. Get top tracks from Spotify
    2. Search YouTube for each track using exact artist+track query
    3. Download and extract embeddings
    4. Average embeddings for artist-level representation
    """
    log(f"Processing artist: {artist_name}")

    # Get tracks from Spotify
    spotify_tracks = get_artist_top_tracks_spotify(spotify_client, artist_name, limit=5)

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
        model="vggish",
    )
```

### 5. Update `run_spike` to Use New Function

```python
def run_spike(custom_artists: Optional[list[str]] = None) -> None:
    # ... existing setup code ...

    # 2. Initialize Spotify client
    log("\n[2/5] Initializing Spotify client...")
    spotify_client = load_spotify_client()
    log("  ✓ Spotify client initialized")

    # 3. Load VGGish model
    log("\n[3/5] Loading VGGish model...")
    vggish_model = load_vggish_model()

    # 4. Extract embeddings using Spotify-guided search
    log("\n[4/5] Extracting embeddings (Spotify-guided YouTube search)...")
    embeddings_db = {}

    for artist in test_artists:
        if not custom_artists and len(embeddings_db) >= 10:
            break

        emb = compute_artist_embedding_v2(
            artist, cache_dir, vggish_model, spotify_client
        )
        if emb:
            embeddings_db[artist] = emb

    # ... rest of validation code ...
```

## Expected Improvements

### Accuracy Improvements
1. **Correct track matching**: Vril gets Vril tracks, not Avril Lavigne
2. **Genre preservation**: Each artist's embeddings reflect their actual music
3. **Similarity variance**: Expected range 0.1-0.9 (vs current 0.83-0.96)

### Validation Against Expectations

After fix, expected results for heterogeneous test set:

| Artist Pair | Genre Difference | Expected Similarity |
|------------|------------------|---------------------|
| deadmau5 ↔ Rezz | Progressive house ↔ Dark techno | 0.6-0.7 (moderate) |
| TroyBoi ↔ IMANU | Trap ↔ Neurofunk dnb | 0.4-0.6 (moderate) |
| **Vril ↔ Sabrina Carpenter** | **Minimal techno ↔ Pop** | **0.1-0.3 (LOW)** ✓ |
| **TroyBoi ↔ Calibre** | **Trap ↔ Liquid dnb** | **0.2-0.4 (LOW)** ✓ |
| **PEEKABOO ↔ Deadmau5** | **Bass ↔ Progressive** | **0.3-0.5 (LOW-MOD)** ✓ |

### Music-Map Overlap
- Current: **0%** overlap
- Expected after fix: **20-40%** overlap (still low due to VGGish limitations, but better than random)

## Implementation Steps

1. **Add Spotify integration** (~30 min)
   - Load client credentials
   - Add `get_artist_top_tracks_spotify()` function

2. **Refactor YouTube search** (~30 min)
   - Add `search_youtube_for_track()` with exact matching
   - Test with problem cases (Vril, PEEKABOO, Calibre)

3. **Update embedding function** (~20 min)
   - Create `compute_artist_embedding_v2()`
   - Wire up Spotify → YouTube pipeline

4. **Test with curated set** (~30 min)
   - Re-run spike with 8 artists
   - Verify correct tracks are found
   - Compare similarity scores to expectations

5. **Save as spike_3** (~5 min)
   - Rename current results to `spike_2_*`
   - Run new spike to generate `spike_3_*` results
   - Document improvements in logs

**Total estimated time**: ~2 hours

## Risks and Mitigations

### Risk 1: Spotify API Rate Limits
- **Mitigation**: Add retry logic with exponential backoff
- **Mitigation**: Cache Spotify lookups to disk

### Risk 2: Artist Name Mismatches
- **Example**: Spotify has "deadmau5" but user searches "Deadmau5"
- **Mitigation**: Use fuzzy matching or normalize names

### Risk 3: YouTube Still Returns Wrong Videos
- **Mitigation**: Add verification step (check uploader, duration, metadata)
- **Mitigation**: Manual review of first few results for each artist

### Risk 4: VGGish May Still Not Differentiate Genres
- **Note**: This fixes data quality, but VGGish has inherent limitations
- **Next Step**: If still poor, consider different embedding models (MusicNN, MERT, Jukebox)

## Success Criteria

1. ✅ **Zero mismatched tracks** for test set (verified in logs)
2. ✅ **Expected low similarities show < 0.5** (Vril-Sabrina, TroyBoi-Calibre, etc.)
3. ✅ **Similarity variance increases** (range > 0.4 vs current 0.13)
4. ✅ **Music-map overlap > 0%** (any improvement shows progress)

## Alternative: Use Spotify Preview URLs Directly

**Note**: Spotify provides 30-second preview URLs for most tracks. We could bypass YouTube entirely:

### Pros
- **Guaranteed correct tracks** (no search ambiguity)
- **Faster** (no YouTube search needed)
- **More reliable** (direct from Spotify)

### Cons
- **Not all tracks have previews** (~70-80% coverage)
- **May require different audio processing** (mp3 vs wav)
- **Spotify terms of service** (check if allowed for ML purposes)

### Implementation Note
The `SpotifyTrack` dataclass already includes `preview_url`. If YouTube continues to be problematic, we can add:

```python
def download_spotify_preview(preview_url: str, output_path: Path) -> bool:
    """Download 30s preview from Spotify."""
    try:
        response = requests.get(preview_url, timeout=30)
        response.raise_for_status()
        with open(output_path, 'wb') as f:
            f.write(response.content)
        return True
    except Exception as e:
        log(f"      ⚠️  Spotify preview download failed: {e}")
        return False
```

This could be a Phase 2 improvement if Spotify-guided YouTube search still has issues.
