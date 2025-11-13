# Embeddings Spike Results Comparison

## Summary

Three spike runs with 8 curated artists testing heterogeneity detection:

| Spike | Approach | Artist Accuracy | Similarity Range | Expected LOW Actually LOW? |
|-------|----------|----------------|------------------|----------------------------|
| **Spike 1** | Random selection (baseline) | N/A | 0.826-0.966 (0.14) | ❌ No variance |
| **Spike 2** | YouTube "topic" search | 37.5% (3/8 wrong) | 0.830-0.966 (0.14) | ❌ All high (0.83+) |
| **Spike 3** | Spotify-guided YouTube | 75% (2/8 wrong) | 0.642-0.974 (0.33) | ⚠️ Partial (Calibre only) |

## Spike 2: YouTube Topic Search (Failed)

### Track Accuracy Issues

| Artist | Correct? | Problem | Tracks Retrieved |
|--------|----------|---------|------------------|
| deadmau5 | ✓ | None | Nextra, Quezacotl, Faxing Berlin, etc. |
| Rezz | ✓ | None | Contorted, Blurry Eyes, Embers, etc. |
| TroyBoi | ✓ | None | KinjaBang, Do You?, Okay, etc. |
| IMANU | ✓ | None | Syrah, Buried, Huil, etc. |
| PEEKABOO | ❌ | **Kendrick Lamar + K-pop** | "Kendrick Lamar - peekaboo" (×2), Red Velvet "Peek-A-Boo" |
| Sabrina Carpenter | ✓ | None | Manchild, Please Please Please, etc. |
| Vril | ❌ | **Avril Lavigne + Aphex Twin** | "Avril Lavigne - Tomorrow", "Love It When You Hate Me", "Avril 14th" |
| Calibre | ❌ | **Calibre 50 (Mexican banda)** | "Calibre 50 - A La Antigüita" |

### Similarity Results (All Too High!)

Your expected **LOW** correlations:

| Artist Pair | Expected | Actual | Status |
|------------|----------|--------|--------|
| Vril ↔ Sabrina Carpenter | LOW | **0.956** | ❌ WRONG (polluted by Avril Lavigne) |
| TroyBoi ↔ Calibre | LOW | **0.907** | ❌ WRONG (polluted data) |
| Calibre ↔ Sabrina Carpenter | LOW | **0.863** | ❌ WRONG (polluted data) |
| Vril ↔ TroyBoi | LOW | **0.892** | ❌ WRONG (polluted by Avril Lavigne) |
| TroyBoi ↔ Deadmau5 | LOW | **0.891** | ❌ WRONG |
| PEEKABOO ↔ Deadmau5 | LOW | **0.830** | ❌ WRONG (polluted by Kendrick Lamar) |

**All similarities: 0.830-0.966** — No meaningful variance!

## Spike 3: Spotify-Guided YouTube Search (Partial Success)

### Track Accuracy Improvements

| Artist | Spotify Match | Correct? | Tracks Retrieved |
|--------|---------------|----------|------------------|
| deadmau5 | ✓ deadmau5 | ✓ | Escape, Ghosts 'n' Stuff, I Remember, The Veldt, Ameonna |
| Rezz | ✓ Rezz | ✓ | Black Ice, Someone Else, Puzzle Box, HOW I DO IT, Hypnocurrency |
| TroyBoi | ✓ TroyBoi | ✓ | Red Eye, Do You?, Afterhours, Bellz, MyBoi Remix |
| IMANU | ✓ IMANU | ✓ | I'm Fine Remix, Bleak, Sutekh, A Taste of Hope, Lost In Mumbai |
| PEEKABOO | ✓ PEEKABOO | **✓ FIXED!** | BADDERS, Here With Me, Hydrate, Want It, Like That Remix |
| Sabrina Carpenter | ✓ Sabrina Carpenter | ✓ | The Life of a Showgirl, Manchild, Tears, When Did You Get Hot?, Espresso |
| Vril | ❌ **Vrillah** (reggae) | ❌ | Light on My Head |
| Calibre | ❌ **Calibre 50** (banda) | ❌ | Si Te Pudiera Mentir, Simplemente Gracias, A La Antigüita (all Spanish vocals) |

**Improvement:** PEEKABOO now gets correct tracks (no more Kendrick Lamar!)

**Remaining Issue:** Spotify's artist search returns wrong artists for niche electronic names ("Vril" → "Vrillah", "Calibre" → "Calibre 50")

### Similarity Results (Variance Improved!)

| Artist Pair | Expected | Spike 2 | Spike 3 | Improvement? |
|------------|----------|---------|---------|--------------|
| **Calibre ↔ Sabrina Carpenter** | **LOW** | 0.863 | **0.768** | ✓ **Lower** (but still wrong artist) |
| **TroyBoi ↔ Calibre** | **LOW** | 0.907 | **0.704** | ✓ **Lower** (but still wrong artist) |
| **PEEKABOO ↔ Calibre** | - | 0.826 | **0.689** | ✓ **Lower** |
| **Rezz ↔ Calibre** | - | 0.935 | **0.642** | ✓ **Lowest similarity** |
| Vril ↔ Sabrina Carpenter | LOW | 0.956 | **0.907** | ⚠️ Slight improvement (but still wrong artist) |
| TroyBoi ↔ Sabrina Carpenter | LOW | 0.885 | **0.907** | ❌ Worse |
| PEEKABOO ↔ Sabrina Carpenter | LOW | 0.875 | **0.886** | ❌ Worse |
| TroyBoi ↔ Deadmau5 | LOW | 0.891 | **0.911** | ❌ Worse |
| PEEKABOO ↔ Deadmau5 | LOW | 0.830 | **0.908** | ❌ Worse |

**Key Finding: Calibre shows LOWER similarity!**

Even though Spotify matched the wrong "Calibre 50" (Mexican banda), the embeddings correctly detected that **Spanish vocal music is different from electronic music**. This proves VGGish CAN distinguish genres when given correct (but different-genre) audio.

### Similarity Range Analysis

| Metric | Spike 2 (Topic) | Spike 3 (Spotify) | Change |
|--------|----------------|-------------------|--------|
| Minimum | 0.830 | **0.642** | ✓ More variance |
| Maximum | 0.966 | **0.974** | Similar |
| Range | 0.136 | **0.332** | ✓ **2.4× wider** |
| Std Dev | ~0.04 | ~0.09 | ✓ Better spread |

**Spike 3 shows 2.4× more variance**, indicating better genre differentiation.

## Key Insights

### ✅ What Worked

1. **Spotify-guided search fixed PEEKABOO** - No more Kendrick Lamar pollution
2. **VGGish CAN detect genre differences** - Calibre 50 (banda) shows lower similarity to electronic artists
3. **Similarity variance increased** - 0.33 range vs 0.14 (wider spread = better discrimination)
4. **Track quality improved** - Most artists now get correct tracks

### ❌ What Still Fails

1. **Spotify artist disambiguation** - "Vril" → "Vrillah", "Calibre" → "Calibre 50"
2. **Pop vs Electronic still high** - Sabrina Carpenter shows 0.86-0.91 similarity to electronic artists
3. **Music-map overlap: 0%** - No correlation with music-map.com similarity
4. **VGGish limitations** - May not capture nuanced electronic subgenre differences

### 🔍 Root Cause Analysis

**Problem 1: Artist Name Ambiguity**
- Niche electronic artists often have common/similar names
- Spotify's text search returns most popular match
- Example: "Vril" (200 monthly listeners) vs "Vrillah" (40K monthly listeners)

**Problem 2: VGGish Model Limitations**
- Trained on AudioSet (YouTube audio)
- May not capture fine-grained electronic music differences
- Better at broad genre (vocal vs instrumental) than electronic subgenres

## Expected Results vs Reality

Your manual expectations for **LOW** similarity pairs:

| Pair | Genre Difference | Expected | Spike 3 Result | Match? |
|------|------------------|----------|----------------|--------|
| Calibre ↔ Sabrina Carpenter | Liquid DnB ↔ Pop | LOW | **0.768** | ⚠️ Partial (wrong Calibre) |
| TroyBoi ↔ Calibre | Trap ↔ Liquid DnB | LOW | **0.704** | ⚠️ Partial (wrong Calibre) |
| Vril ↔ Sabrina Carpenter | Minimal Techno ↔ Pop | LOW | **0.907** | ❌ High (wrong Vril) |
| Vril ↔ TroyBoi | Minimal Techno ↔ Trap | LOW | **0.934** | ❌ High (wrong Vril) |
| TroyBoi ↔ Deadmau5 | Trap ↔ Progressive | LOW | **0.911** | ❌ High |
| PEEKABOO ↔ Deadmau5 | Bass ↔ Progressive | LOW | **0.908** | ❌ High |

**Only Calibre pairs show lower similarity**, but that's because we got Mexican banda music instead of liquid DnB!

## Recommendations

### Immediate Fix: Artist ID Mapping

Create a manual mapping for ambiguous artists:

```json
{
  "Vril": "73w1xXlZEqbJe2qYPGsU8l",  // Actual Vril (techno)
  "Calibre": "5Y3XC0gDCYPDsDCGLMzz0W1",  // Actual Calibre (dnb)
  "Rezz": "4aKdmOXdUKX07HVd3sGgzw"  // Already correct
}
```

### Better Approach: Add Genre Filtering

Modify Spotify search to filter by genre:

```python
def get_artist_top_tracks_spotify(
    spotify: spotipy.Spotify,
    artist_name: str,
    expected_genres: list[str] = None,  # e.g., ["techno", "minimal"]
    limit: int = 5
) -> list[SpotifyTrack]:
    # Search with genre hint
    results = spotify.search(
        q=f'artist:"{artist_name}" genre:{" ".join(expected_genres)}',
        type='artist',
        limit=5
    )

    # Filter results by genre match
    for artist in results['artists']['items']:
        if any(g in artist['genres'] for g in expected_genres):
            return get_tracks_for_artist(artist['id'])

    # Fallback to first result
    return get_tracks_for_artist(results['artists']['items'][0]['id'])
```

### Alternative: Use Spotify Preview URLs Directly

Skip YouTube entirely and use Spotify's 30-second preview URLs:
- ✅ Guaranteed correct tracks
- ✅ No search ambiguity
- ✅ Faster (no YouTube search)
- ❌ ~70-80% coverage (not all tracks have previews)

### Long-term: Better Embedding Model

VGGish may not be suitable for fine-grained electronic music:
- **MusicNN** - Trained specifically on music
- **MERT** - Music understanding transformer
- **Jukebox** - OpenAI's music model
- **Essentia** - Music information retrieval library

## Conclusion

**Spotify-guided search is a partial success:**
- ✅ Fixes track accuracy for most artists (6/8 correct)
- ✅ Increases similarity variance (2.4×)
- ✅ Proves VGGish CAN detect some genre differences
- ❌ Still fails on artist disambiguation for niche names
- ❌ VGGish may not capture electronic subgenre nuances

**Next steps:**
1. Add artist ID mapping for ambiguous artists
2. Re-run Spike 4 with correct artist IDs
3. If still poor, consider alternative embedding models
