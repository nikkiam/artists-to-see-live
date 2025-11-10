# Embeddings Spike - Readiness Check

## Status: ✅ READY TO START

---

## Pre-Spike Verification

### 1. Data Sources ✅

**Music-Map Data (for validation)**
- ✅ File exists: `output/similar_artists_map.json`
- ✅ Format verified: JSON with artist names and similar_artists arrays
- ✅ Size: ~184k lines, substantial dataset for validation
- ✅ Structure:
  ```json
  {
    "Artist Name": {
      "status": "success",
      "similar_artists": [
        {"name": "Similar Artist", "rank": 1, "relationship_strength": 14.6681}
      ]
    }
  }
  ```

**Spotify Integration**
- ✅ Credentials configured: `spotify-config.json` exists
- ✅ Working code example: `src/extract_artists_from_spotify_playlists.py`
- ✅ Has refresh token mechanism for long-running tasks
- ✅ Successfully used in production for playlist extraction

### 2. Dependencies Status

**Currently Installed:**
- ✅ numpy >= 1.24.0
- ✅ requests >= 2.32.5
- ✅ beautifulsoup4, lxml (HTML parsing)

**Need to Install:**
- ❌ librosa (audio processing)
- ❌ soundfile (audio I/O)
- ❌ scikit-learn (cosine similarity)
- ❌ spotipy (Spotify SDK - optional, can use requests directly)
- ❌ openl3 (pre-trained embedding model)

**Installation Command:**
```bash
uv add librosa soundfile scikit-learn spotipy openl3
```

### 3. Project Standards Compliance ✅

**Logging (CLAUDE.md requirements)**
- ✅ Plan uses file logging only (no print statements)
- ✅ Logs will be committed to git
- ✅ Log file: `embeddings_experiments/logs/spike_YYYY-MM-DD.log`
- ✅ Structured format with timestamps and progress markers

**Code Style**
- ✅ Plan uses frozen dataclasses for immutable data
- ✅ Functional programming style (pure functions where possible)
- ✅ Early exit pattern for error handling
- ✅ Type hints for all function signatures
- ✅ No print() statements (Ruff T201 will enforce)

### 4. Directory Structure ✅

```
embeddings_experiments/
├── README.md                 ✅ Created
├── recommendations.md        ✅ Created
├── spike_plan.md            ✅ Created
├── READINESS_CHECK.md       ✅ This file
├── logs/                    ⏳ Will be created on first run
│   └── spike_YYYY-MM-DD.log
├── data/                    ⏳ Will be created during spike
│   ├── audio_cache/         (downloaded previews)
│   ├── spike_embeddings.json
│   ├── spike_similarities.json
│   └── spike_validation.json
└── spike.py                 ❌ To be implemented
```

### 5. Test Artist Selection ✅

**Criteria for Selection:**
- Artists with `status: "success"` in music-map data
- Mix of popularity levels
- Diverse within electronic/techno/house genres
- Known to have Spotify presence

**Candidates (from music-map data):**
Can select from ~1307 artists in `similar_artists_map.json`

---

## Next Steps

### Immediate (Before Starting Spike)

1. **Install dependencies:**
   ```bash
   cd /Users/nikki/dev/artists-to-see-live
   uv add librosa soundfile scikit-learn spotipy openl3
   ```

2. **Verify OpenL3 installation:**
   ```bash
   uv run python -c "import openl3; print('OpenL3 loaded successfully')"
   ```

3. **Create spike.py script** (see `spike_plan.md` for structure)

### During Spike

1. Run: `uv run python -m embeddings_experiments.spike`
2. Monitor: `tail -f embeddings_experiments/logs/spike_*.log` (optional)
3. Wait ~30-45 minutes for completion

### After Spike

1. Review logs: `cat embeddings_experiments/logs/spike_*.log`
2. Check results: `cat embeddings_experiments/data/spike_validation.json`
3. Validate against success criteria
4. Decide: Proceed to Phase 2 or iterate

---

## Success Criteria Reminder

- ✅ Embedding extraction success rate ≥ 85%
- ✅ Pearson correlation with music-map.com ≥ 0.6
- ✅ Top-5 overlap with music-map.com ≥ 50%
- ✅ All work follows project standards (logging, dataclasses, functional style)

---

## Risk Assessment

**Low Risk:**
- ✅ Spotify integration already proven
- ✅ Music-map data available and well-structured
- ✅ OpenL3 is well-documented and stable
- ✅ Audio processing is standard (librosa)

**Medium Risk:**
- ⚠️ Spotify preview availability (typically 80-90%, should be fine)
- ⚠️ OpenL3 model download (happens automatically on first run, may take time)
- ⚠️ Audio processing errors (handle gracefully with try/except)

**Mitigations:**
- Try multiple tracks per artist if previews unavailable
- Log all errors for debugging
- Early exit pattern prevents cascading failures
- Manual review of results ensures quality

---

## Time Estimate

- Dependencies installation: **5-10 minutes**
- Implement spike.py: **2-3 hours**
- Run spike (10 artists): **30-45 minutes**
- Review results: **30 minutes**

**Total: 4-5 hours**

---

## Decision: Proceed?

**Recommendation: ✅ YES - All prerequisites met**

The project is ready to proceed with the embeddings spike. All necessary data sources are in place, the approach is well-planned, and the infrastructure follows project standards.

**Next Action:** Install dependencies and implement `spike.py`
