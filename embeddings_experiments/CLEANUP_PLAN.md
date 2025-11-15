# Embeddings Experiments Cleanup Plan

## Files to KEEP

### Core Scripts (Production/Future Use)
- `spike_6_mert_hf.py` - Current working MERT implementation with Layer 11
- `mert_server.py` - FastAPI server for MERT inference
- `analyze_spike_6.py` - Comprehensive analysis tool
- `find_artist_ids.py` - Artist ID disambiguation utility
- `artist_id_mapping.json` - Manual artist mappings

### Documentation (Keep for Reference)
- `README.md` - Main documentation
- `SPIKE_6_RESULTS.md` - Final results and recommendations
- `SPIKE_6_PLAN.md` - Context for Spike 6 approach
- `SPIKE_5_MERT_RESULTS.md` - Why chunking failed (important context)
- `FINAL_RESULTS.md` - Spike 4 results for comparison
- `SPIKE_COMPARISON.md` - Historical comparison
- `recommendations.md` - Architecture recommendations

### Docker/Deployment (Move to docker/ folder)
- `Dockerfile` - MERT inference endpoint Docker image
- `DOCKER_DEPLOYMENT_GUIDE.md` - Deployment instructions
- `GITHUB_ACTION_SETUP.md` - GitHub Actions setup
- `SPIKE_6_GITHUB_ACTION_SUMMARY.md` - Deployment summary
- `DEPLOYMENT_OPTIONS.md` - Deployment options comparison
- `QUICK_START.md` - Quick start guide

### Data Files (Keep Recent/Useful)
- `data/spike_6_track_embeddings.json` - Current embeddings (12MB)
- `data/spike_6_layer_similarities.json` - Layer similarities (89KB)
- `data/spike_6_detailed_analysis.json` - Analysis results
- `data/spike_5_similarities.json` - For comparison in analysis
- `data/spike_4_similarities.json` - VGGish comparison baseline
- `data/spike_6_embedding_cache.json` - Cache (12MB)

### Config Files
- `.env` - Environment variables (keep but ensure in .gitignore)
- `.cache` - HuggingFace cache (keep)

---

## Files to REMOVE

### Obsolete Scripts (Old Techniques)
- `spike.py` - Old general-purpose spike script (VGGish-focused, replaced by spike_6_mert_hf.py)
- `spike_5_mert.py` - Chunked MERT implementation (failed approach)
- `quick_validation.py` - One-off validation script

### HuggingFace Spaces Scripts (Not Using Spaces, Using Endpoints)
- `setup_hf_space.py` - Spaces deployment (failed, using Endpoints instead)
- `deploy_to_hf_spaces.py` - Spaces deployment
- `cleanup_hf_space.py` - Spaces cleanup
- `SPIKE_6_SPACES_SETUP.md` - Spaces setup guide (failed approach)

### Old Planning Documents (Archived)
- `spike_plan.md` - Original spike plan (superseded)
- `SPIKE_5_PLAN.md` - Spike 5 plan (completed, context in results)
- `READINESS_CHECK.md` - Pre-spike checklist (completed)
- `SEARCH_FIX_PLAN.md` - Search fix plan (completed in Spike 3/4)
- `OPUS_4.1_EVALUTATION_ON_FINAL_RESULTS.md` - One-off evaluation

### Old Data Files (Spikes 1-3, Failed Approaches)
- `data/spike_1_*.json` - Random selection baseline (obsolete)
- `data/spike_2_*.json` - YouTube topic search (polluted data)
- `data/spike_3_*.json` - Spotify-guided search (still had issues)
- `data/spike_5_embeddings.json` - Chunked MERT (failed approach)
- `data/spike_5_validation.json` - Validation for failed approach
- `data/spike_4_embeddings.json` - VGGish embeddings (keep similarities only)
- `data/spike_4_validation.json` - VGGish validation (keep similarities only)

### Cache/Temp (Already Cleaned)
- `data/audio_cache/` - Already deleted
- `data/spotify-12m-songs.zip` - Deprecated dataset (97MB)
- `data/tracks_features.csv` - Deprecated Spotify features (330MB)

---

## Proposed New Structure

```
embeddings_experiments/
├── README.md                           # Updated main docs
├── docker/                             # NEW: Docker deployment files
│   ├── Dockerfile
│   ├── DEPLOYMENT_GUIDE.md
│   ├── GITHUB_ACTION_SETUP.md
│   ├── DEPLOYMENT_OPTIONS.md
│   ├── QUICK_START.md
│   └── SPIKE_6_DEPLOYMENT_SUMMARY.md
├── docs/                               # NEW: Historical/reference docs
│   ├── SPIKE_COMPARISON.md
│   ├── SPIKE_4_RESULTS.md (renamed from FINAL_RESULTS.md)
│   ├── SPIKE_5_RESULTS.md
│   ├── SPIKE_5_PLAN.md
│   ├── SPIKE_6_PLAN.md
│   ├── SPIKE_6_RESULTS.md
│   └── recommendations.md
├── scripts/                            # NEW: Core scripts
│   ├── spike_6_mert_hf.py             # Main MERT implementation
│   ├── mert_server.py                 # FastAPI server
│   ├── analyze_spike_6.py             # Analysis tool
│   └── find_artist_ids.py             # Utility
├── data/
│   ├── spike_6_track_embeddings.json
│   ├── spike_6_layer_similarities.json
│   ├── spike_6_embedding_cache.json
│   ├── spike_6_detailed_analysis.json
│   ├── spike_5_similarities.json      # For comparison
│   ├── spike_4_similarities.json      # For comparison
│   └── artist_id_mapping.json
├── logs/                               # Keep existing logs
└── .env                                # Environment config

REMOVED:
- All spike 1-3 data files
- All HuggingFace Spaces scripts
- spike.py (old general-purpose script)
- spike_5_mert.py (chunked approach)
- Old planning docs
```

---

## Cleanup Commands

```bash
# Create new folders
mkdir -p docker docs scripts

# Move Docker files
mv Dockerfile docker/
mv DOCKER_DEPLOYMENT_GUIDE.md docker/DEPLOYMENT_GUIDE.md
mv GITHUB_ACTION_SETUP.md docker/
mv DEPLOYMENT_OPTIONS.md docker/
mv QUICK_START.md docker/
mv SPIKE_6_GITHUB_ACTION_SUMMARY.md docker/DEPLOYMENT_SUMMARY.md

# Move docs
mv SPIKE_COMPARISON.md docs/
mv FINAL_RESULTS.md docs/SPIKE_4_RESULTS.md
mv SPIKE_5_MERT_RESULTS.md docs/SPIKE_5_RESULTS.md
mv SPIKE_5_PLAN.md docs/
mv SPIKE_6_PLAN.md docs/
mv SPIKE_6_RESULTS.md docs/
mv recommendations.md docs/

# Move scripts
mv spike_6_mert_hf.py scripts/
mv mert_server.py scripts/
mv analyze_spike_6.py scripts/
mv find_artist_ids.py scripts/

# Move artist mapping to data
mv artist_id_mapping.json data/

# Remove obsolete scripts
rm spike.py
rm spike_5_mert.py
rm quick_validation.py
rm setup_hf_space.py
rm deploy_to_hf_spaces.py
rm cleanup_hf_space.py

# Remove obsolete docs
rm spike_plan.md
rm READINESS_CHECK.md
rm SEARCH_FIX_PLAN.md
rm OPUS_4.1_EVALUTATION_ON_FINAL_RESULTS.md
rm SPIKE_6_SPACES_SETUP.md

# Remove old data files
rm data/spike_1_*.json
rm data/spike_2_*.json
rm data/spike_3_*.json
rm data/spike_5_embeddings.json
rm data/spike_5_validation.json
rm data/spike_4_embeddings.json
rm data/spike_4_validation.json

# Remove deprecated datasets (if still present)
rm -f data/spotify-12m-songs.zip
rm -f data/tracks_features.csv
```

## Space Savings

- Old spike data (1-3): ~150KB
- Old embeddings (4-5): ~200KB
- Deprecated datasets: ~427MB (if present)
- Old scripts: ~45KB

**Total savings**: ~427MB + old data files
