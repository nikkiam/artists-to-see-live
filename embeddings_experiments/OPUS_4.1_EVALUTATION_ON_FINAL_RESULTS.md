Looking at your results, you've done excellent systematic testing! The core issue is clear: VGGish was trained on AudioSet for general audio event detection (baby crying, glass breaking, "music" as a single category), not for music similarity. Your 0.711 similarity between Vril and Sabrina Carpenter vs 0.928 between Vril and Calibre perfectly illustrates this - VGGish can barely tell minimal techno from liquid dnb despite them being worlds apart (120 BPM sparse loops vs 170+ BPM complex breakbeats).

## Immediate Recommendation: Yes, Try PaSST

With your RTX 2060, you should definitely try **PaSST** (Patchout Audio Spectrogram Transformer). Here's why it's perfect for your use case:

1. **Trained on AudioSet BUT with better architecture** - Uses Vision Transformer which captures longer-range dependencies crucial for music structure
2. **Much higher dimensional embeddings** (768-dim vs VGGish's 128-dim) - More room to encode subtle differences
3. **Your GPU is sufficient** - RTX 2060's 6GB VRAM can handle PaSST inference comfortably
4. **Better temporal modeling** - Critical for distinguishing rhythm patterns (drum patterns in dnb vs 4/4 techno kicks)

## Even Better Options for Electronic Music

### 1. **Music2Vec or MERT** (Best for your use case)
These are music-specific transformers that understand musical concepts:
- MERT-95M would run fine on your 2060
- Trained specifically on music, not general audio
- Can capture harmonic progressions, rhythm patterns, timbre differences
- Much better at subgenre distinction

### 2. **Discogs-Effnet** 
- Trained on 1.8M tracks from Discogs (electronic music heavy!)
- Specifically designed for music tagging and genre classification
- Lighter weight than transformers, fast on your hardware
- Available through Essentia

### 3. **Hybrid Approach with Spotify Features**
Since you're already using Spotify API, combine:
```python
# Spotify audio features
tempo_diff = abs(track1.tempo - track2.tempo)
energy_diff = abs(track1.energy - track2.energy)
key_compatibility = key_distance(track1.key, track2.key)

# Weight by genre importance
if both_electronic:
    tempo_weight = 0.3  # BPM matters more in electronic
    energy_weight = 0.2
    embedding_weight = 0.5
```

## Practical Implementation Path

### Step 1: Quick Win with Essentia (Tomorrow)
```bash
pip install essentia-tensorflow
```
Use their Discogs-Effnet model - it's specifically trained on electronic music and will immediately give better results than VGGish.

### Step 2: PaSST on Ubuntu (This Weekend)  
Your RTX 2060 setup:
```bash
# Don't need full Ubuntu - WSL2 works great
sudo apt update
sudo apt install python3-pip ffmpeg
pip install hear21passt
```

### Step 3: Add Musical Knowledge Constraints
For electronic music specifically:
- **Tempo bands**: 120-130 (techno), 140 (dubstep), 170-180 (dnb)
- **Harmonic content**: Minimal techno = fewer harmonic changes
- **Percussion density**: Breakbeats vs four-on-floor
- **Frequency emphasis**: Sub-bass presence in dubstep/dnb

## The Real Issue: Music-Map.com Uses Graph Data

Music-Map likely uses collaborative filtering and artist co-occurrence data, not just audio. Consider:
1. Artists who play at the same events
2. Artists on the same labels  
3. User listening patterns
4. DJ set tracklists

For discovering artists at local underground events, you might want to supplement embeddings with:
- Event lineup co-occurrences (artists playing the same nights)
- Label relationships (Drumcode artists are similar)
- DJ chart data (artists playing each other's tracks)

## My Recommendation Priority

1. **Try Discogs-Effnet via Essentia first** (1 hour setup, likely 50% improvement)
2. **Test PaSST if Essentia doesn't give enough granularity** (better for capturing rhythm)
3. **Add Spotify audio features as additional signals**
4. **Consider building a small graph of artist relationships from your local scene**

Your Calibre/Vril confusion perfectly shows VGGish's limits - those artists are nothing alike despite both being "electronic". A music-specific model should easily separate 170 BPM liquid rollers from 125 BPM Berlin minimal!
