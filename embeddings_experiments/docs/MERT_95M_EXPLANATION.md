# Understanding MERT-95M: A 200-Level CS Explanation

## Target Audience
CS students who have completed a 100-level introduction to neural networks covering:
- Forward propagation and backpropagation
- Layers, weights, and activation functions
- Basic loss functions and gradient descent
- Simple architectures (fully connected networks, CNNs)

## What is MERT-95M?

**MERT-95M** (Music Understanding Model with Large-Scale Self-Supervised Training) is a transformer-based neural network designed specifically for understanding music audio. The "95M" refers to 95 million parameters.

**Key Insight**: While a typical neural network might classify an audio clip as "rock" or "jazz", MERT creates a mathematical representation (embedding) that captures the **musical essence** of the audio - rhythm, timbre, harmony, and production style.

---

## Comparison to Typical Neural Networks

### 1. Architecture: Transformer vs. Convolutional

#### Typical Audio Neural Network (e.g., VGGish)
```
Audio → Spectrogram → [Conv Layer] → [Conv Layer] → [Pool] → [Dense] → Output
                       ↓                ↓              ↓         ↓
                     Local patterns   Larger patterns  Reduce   Classify
```

**How it works:**
- **Convolutional layers** scan small windows of the spectrogram
- Like detecting edges in an image, but for audio frequency patterns
- Each layer detects increasingly complex patterns
- **Pooling layers** reduce dimensionality
- Final **dense layer** produces classification or embedding

**Limitation**: Convolution has a **local receptive field** - it only "sees" small time windows at once. To understand a 30-second song, it must stack many layers, making it hard to capture long-term musical structure.

#### MERT-95M (Transformer-based)
```
Audio → Acoustic Tokens → [Transformer Layer 1] → [Transformer Layer 2] → ... → [Layer 13]
                           ↓                        ↓                           ↓
                         Self-Attention         Self-Attention              Self-Attention
                         (sees all tokens)      (sees all tokens)           (sees all tokens)
```

**How it works:**
- Audio is converted into **acoustic tokens** (discrete representations)
- **Self-attention mechanism** allows each position to "look at" all other positions
- Every layer can see the **entire 30-second context** simultaneously
- No need to stack many layers just to see long-range patterns

**Key Advantage**: MERT can relate a drum hit at 5 seconds to a melody at 25 seconds directly, capturing musical coherence across the full song.

---

## Core Innovation #1: Self-Attention

### What is Self-Attention?

Imagine you're reading a sentence: "The cat sat on the mat because **it** was tired."

To understand what "it" refers to, you need to look back at "the cat". Self-attention is a mechanism that lets the model do this automatically.

### How Self-Attention Works (Simplified)

For each position in the input:
1. **Query**: "What am I looking for?"
2. **Key**: "What do I represent?"
3. **Value**: "What information do I carry?"

**Step-by-step:**
```python
# For each token in the audio sequence
for token_i in tokens:
    # 1. Create query vector for this token
    query_i = weights_Q @ token_i

    # 2. Compare query to all tokens' keys
    for token_j in tokens:
        key_j = weights_K @ token_j

        # 3. Compute attention score: how relevant is token_j to token_i?
        score_ij = query_i · key_j  # Dot product

    # 4. Softmax to get attention weights (sum to 1)
    attention_weights = softmax(all_scores)

    # 5. Weighted sum of value vectors
    output_i = sum(attention_weights[j] * value_j for all j)
```

**In Music Context:**
- A bass note at time=10s might have high attention to drum hits at time=10.5s, 11s, 11.5s
- A vocal melody might attend to its harmonic accompaniment
- The model learns which parts of the song relate to each other

**Why This Matters**: Unlike convolution (which only sees nearby time steps), self-attention can connect **any two points** in the 30-second clip, regardless of distance.

---

## Core Innovation #2: Transformer Layers

### What is a Transformer Layer?

A transformer layer combines self-attention with feed-forward processing:

```
Input (768-dimensional vectors for each time step)
    ↓
[Self-Attention]  ← Look at all other time steps
    ↓
[Add & Normalize]  ← Residual connection + normalization
    ↓
[Feed-Forward NN]  ← Dense layers with ReLU activation
    ↓
[Add & Normalize]  ← Another residual connection
    ↓
Output (768-dimensional vectors for each time step)
```

**Key Components:**

1. **Residual Connections** (`Add`):
   ```python
   output = layer_processing(input) + input
   ```
   - Helps gradients flow during training
   - Allows network to learn **refinements** rather than rebuilding from scratch

2. **Layer Normalization**:
   - Stabilizes training by normalizing activations
   - Prevents values from exploding or vanishing

3. **Feed-Forward Network**:
   ```python
   hidden = ReLU(W1 @ x + b1)
   output = W2 @ hidden + b2
   ```
   - Two dense layers with ReLU activation
   - Processes each time step independently
   - Provides non-linear transformations

### MERT Has 13 Transformer Layers

```
Layer 0 (Input)  → Basic audio features
Layer 1          → Low-level patterns (rhythm, pitch)
Layer 2          → Short-term musical phrases
...
Layer 6          → Musical motifs and progressions
...
Layer 10         → Artist-specific production style ⭐
Layer 11         → High-level artist similarity ⭐⭐ (OPTIMAL)
Layer 12         → Abstract musical concepts
Layer 13 (Final) → General music understanding
```

**Key Finding from This Project**:
- **Layer 11 is optimal** for artist similarity, not Layer 13!
- Early layers (1-2) capture discriminative features
- Middle layers (5-6) are least discriminative
- Late layers (10-12) capture high-level style

This is **different from CNNs** where final layers are typically best for classification.

---

## Core Innovation #3: Self-Supervised Pre-Training

### The Training Challenge

**Problem**: Labeling music is expensive and subjective
- Is this song "rock" or "alternative rock" or "indie rock"?
- Does this artist sound like X or Y? (Subjective!)

**Solution**: Self-supervised learning - the model learns from the audio itself

### How MERT Was Trained (Self-Supervised)

MERT uses a technique called **masked acoustic modeling**:

```
Original:  [drum] [bass] [synth] [vocal] [guitar] [drums]
Masked:    [drum] [MASK] [synth] [MASK]  [guitar] [drums]
Task:      Predict the masked tokens
```

**Step-by-step:**
1. Take a music audio clip
2. Convert to acoustic tokens (discrete representations)
3. **Randomly mask** some tokens (hide them)
4. Train the model to **predict** the masked tokens from context
5. Model learns musical structure and relationships

**Why This Works:**
- The model must understand music to predict masked parts
- No human labels needed - learns from millions of songs
- Similar to how BERT works for text (predict masked words)

**Training Scale**: MERT was trained on **160,000 hours** of music across many genres, which is why it understands diverse musical styles.

---

## Core Innovation #4: Acoustic Tokenization

### From Continuous Audio to Discrete Tokens

**Challenge**: Audio is continuous (infinite possible values), but transformers work best with discrete tokens (like words in text).

**Solution**: Learn a **discrete codebook** of acoustic patterns

```
Raw Audio (continuous waveform)
    ↓
Convert to Mel Spectrogram (time-frequency representation)
    ↓
Acoustic Encoder (neural network)
    ↓
Vector Quantization (match to nearest codebook entry)
    ↓
Discrete Acoustic Tokens (like "words" of music)
```

**Example Analogy**:
- Text: "The cat sat" → [token_234, token_567, token_891]
- Audio: [bass drum, snare, hi-hat] → [token_42, token_78, token_103]

**Why This Matters**:
- Discrete tokens are easier for transformers to process
- Reduces computational complexity
- Enables masked prediction training (can't mask continuous values)

---

## The Full MERT-95M Pipeline

### End-to-End Processing

```python
# Input: 30 seconds of audio (720,000 samples at 24kHz)
audio = load_audio("song.mp3", duration=30, sr=24000)

# Step 1: Convert to mel spectrogram
# Output: [time_steps, 128 mel_frequencies]
spectrogram = mel_spectrogram(audio)

# Step 2: Acoustic tokenization
# Output: [time_steps, hidden_dim]
acoustic_features = acoustic_encoder(spectrogram)

# Step 3: Vector quantization
# Output: [time_steps] with discrete token IDs
tokens = vector_quantize(acoustic_features)

# Step 4: Embedding lookup
# Output: [time_steps, 768]
embeddings = embedding_layer(tokens)

# Step 5: Add positional encoding
# Output: [time_steps, 768]
# Tells model where each token is in time
embeddings = embeddings + positional_encoding

# Step 6: Process through 13 transformer layers
hidden_states = embeddings
for layer in range(13):
    # Self-attention: relate all time steps to each other
    attention_output = self_attention(hidden_states)
    hidden_states = layer_norm(hidden_states + attention_output)

    # Feed-forward: process each time step
    ff_output = feed_forward(hidden_states)
    hidden_states = layer_norm(hidden_states + ff_output)

    # Save this layer's output
    layer_outputs[layer] = hidden_states

# Step 7: Extract embeddings
# For this project: Use Layer 11 output
# Output: [time_steps, 768]
layer_11_output = layer_outputs[11]

# Step 8: Aggregate over time (mean pooling)
# Output: [768] - single vector representing the entire 30s
final_embedding = mean(layer_11_output, axis=0)
```

### Output: 768-Dimensional Embedding Vector

```python
embedding = [0.23, -0.45, 0.67, ..., 0.12]  # 768 numbers
```

This vector encodes:
- Rhythm patterns and tempo
- Harmonic structure
- Timbral characteristics (bright vs dark, harsh vs smooth)
- Production style (mixing, mastering, sound design)
- Musical structure and coherence

**Similar artists** will have embeddings that are **close together** in this 768-dimensional space.

---

## Key Architectural Differences from Typical Neural Networks

| Feature | Typical CNN (VGGish) | MERT-95M |
|---------|---------------------|----------|
| **Architecture** | Convolutional + Pooling | Transformer (Self-Attention) |
| **Receptive Field** | Local (grows with depth) | Global (all positions from layer 1) |
| **Context Window** | Limited by layer depth | Full 30 seconds at every layer |
| **Input Type** | Continuous spectrogram | Discrete acoustic tokens |
| **Training** | Supervised (needs labels) | Self-supervised (learns from data) |
| **Output Layers** | Final layer best | Layer 11 best for artist similarity |
| **Parameters** | ~70M (VGGish) | 95M (MERT) |
| **Temporal Modeling** | Implicit (via convolution) | Explicit (via attention) |

---

## Why Chunking Breaks MERT (Spike 5 Problem)

### The Chunking Problem

In Spike 5, MERT was run on a memory-limited M1 Mac, requiring 10-second chunks:

```python
# BAD: Spike 5 approach
audio = load_audio("song.mp3", duration=30)
chunks = split_into_chunks(audio, chunk_size=10)  # [0-10s, 10-20s, 20-30s]

# Process each chunk separately
embeddings = []
for chunk in chunks:
    emb = mert_model(chunk)  # Only sees 10 seconds
    embeddings.append(emb)

# Average the chunk embeddings
final_embedding = mean(embeddings)  # DESTROYS temporal coherence!
```

**Why This Fails:**

1. **Lost Long-Range Dependencies**:
   - Chorus at 5s can't relate to chorus at 25s
   - Musical structure (verse-chorus-verse) is invisible
   - Each chunk is processed independently

2. **Averaging Destroys Information**:
   ```python
   # Imagine these chunk embeddings (simplified to 2D):
   chunk_1 = [0.9, 0.1]  # Verse (low energy)
   chunk_2 = [0.1, 0.9]  # Chorus (high energy)
   chunk_3 = [0.9, 0.1]  # Verse (low energy)

   average = [0.63, 0.37]  # Generic, loses verse-chorus distinction!
   ```

3. **Results**:
   - Spike 5 (chunked): 0.808-0.971 similarity (everything too similar!)
   - Spike 6 (full context): 0.493-0.773 similarity (72% better discrimination!)

**The Fix**: Use proper GPU infrastructure to process full 30-second clips:

```python
# GOOD: Spike 6 approach
audio = load_audio("song.mp3", duration=30)
embedding = mert_model(audio)  # Full context, no chunking!
```

---

## Real-World Results from This Project

### Experiment Setup
- **Artists**: 8 (deadmau5, Rezz, TroyBoi, IMANU, PEEKABOO, Sabrina Carpenter, Vril, Calibre)
- **Tracks**: 40 total (5 per artist)
- **Similarity Metric**: Cosine similarity between Layer 11 embeddings

### Layer 11 Performance (Optimal)

| Artist Pair | Genre Difference | Similarity | Interpretation |
|-------------|------------------|------------|----------------|
| **PEEKABOO ↔ Vril** | Bass ↔ Minimal Techno | **0.493** | Very different (good!) |
| **IMANU ↔ Vril** | Neurofunk DnB ↔ Minimal | **0.518** | Very different |
| **Vril ↔ Sabrina** | Minimal Techno ↔ Pop | **0.610** | Different |
| **TroyBoi ↔ Calibre** | Trap ↔ Liquid DnB | **0.686** | Somewhat different |
| **deadmau5 ↔ Rezz** | Progressive ↔ Dark Techno | **0.703** | Similar (both electronic) |
| **IMANU ↔ Sabrina** | Neurofunk DnB ↔ Pop | **0.773** | Most similar (high production?) |

**Similarity Range**: 0.493 - 0.773 (span: **0.280**)

**Comparison to VGGish (Spike 4)**:
- VGGish span: 0.263
- MERT Layer 11 span: 0.280 (+6% improvement)
- But MERT provides richer semantic understanding

**Comparison to Chunked MERT (Spike 5)**:
- Chunked span: 0.163
- Full context span: 0.280 (+72% improvement!)
- Chunking was the problem, not MERT itself

---

## Understanding the Embedding Space

### What Does "Similarity" Mean?

Cosine similarity measures the angle between two vectors:

```python
embedding_1 = [0.5, 0.8, 0.3, ...]  # 768 dimensions
embedding_2 = [0.6, 0.7, 0.2, ...]  # 768 dimensions

# Cosine similarity = cos(angle between vectors)
similarity = cosine_similarity(embedding_1, embedding_2)

# Returns a value between -1 (opposite) and 1 (identical)
# In practice: 0.493 (very different) to 0.773 (similar)
```

**Geometric Interpretation:**
- **0.9-1.0**: Nearly identical production style
- **0.7-0.9**: Similar genre/subgenre
- **0.5-0.7**: Different subgenres, some shared characteristics
- **0.3-0.5**: Very different genres
- **<0.3**: Completely different (would be rare in music)

### Visualizing the Embedding Space (2D Projection)

If we project the 768-dimensional embeddings to 2D using t-SNE:

```
    Sabrina Carpenter (Pop)
           |
           |
    deadmau5 ---- Rezz
    (Progressive)  (Dark Techno)
           |
           |
    TroyBoi ----- IMANU
    (Trap)        (Neurofunk DnB)
           |
           |
    PEEKABOO      Calibre
    (Bass)        (Liquid DnB)
           |
           |
         Vril
    (Minimal Techno)
```

Artists with similar sound cluster together in this high-dimensional space.

---

## Limitations and Trade-offs

### What MERT Does Well ✅
- **Subgenre discrimination**: Bass vs Minimal Techno (0.493 similarity)
- **Production style**: Identifies similar mixing/mastering
- **Musical structure**: Understands verse-chorus patterns
- **Genre-agnostic**: Works across electronic, pop, rock, jazz, etc.

### What MERT Doesn't Capture ❌
- **Artist networks**: Who collaborates with whom
- **Scene relationships**: Artists from the same label/location
- **Cultural context**: Why fans of X also like Y
- **Listening behavior**: What people actually listen to together

**Key Finding**: MERT had **0% overlap** with music-map.com recommendations

**Why?**
- Music-map uses collaborative filtering (user listening patterns)
- MERT uses audio analysis (production and sound)
- **These are different types of similarity!**

Example:
- **Music-map says**: Vril is similar to Prince of Denmark, Traumprinz (same minimal techno scene)
- **MERT says**: Vril is similar to Sabrina Carpenter (both have polished production?)

Both are valid, but for different use cases!

---

## Computational Complexity

### Memory Requirements

**Full 30-second processing:**
```
Audio: 30s × 24,000 Hz = 720,000 samples
Tokens: ~1,500 time steps (after downsampling)
Embedding: 1,500 × 768 = 1.152M values per layer
All 13 layers: 1.152M × 13 = ~15M values
```

**Why GPU is needed:**
- Self-attention is O(n²) where n = sequence length
- For 1,500 tokens: 1,500² = 2.25M attention computations per layer
- Total: 2.25M × 13 layers = 29.25M computations
- Plus feed-forward networks for each token

**M1 Mac (Spike 5)**: 8GB unified memory → Had to chunk to 10s
**A10G GPU (Spike 6)**: 24GB VRAM → Can process full 30s

### Inference Time

- **Local M1 Mac** (chunked): 1.5 minutes per track
- **A10G GPU** (full context): ~10 seconds per track (9× faster!)

### Cost (HuggingFace Inference Endpoints)
- **A10G GPU**: $1.05/hour
- **Per track** (~10s inference): $0.003
- **1,000 artists** (5 tracks each): ~$15

Affordable for production use!

---

## Summary: Key Takeaways for CS Students

1. **Transformers use self-attention** to see the entire input at once, unlike CNNs which have local receptive fields

2. **Self-attention relates all positions** to each other, critical for understanding long-range structure in music

3. **Not all layers are equal**: Layer 11 is optimal for artist similarity in MERT, not the final layer

4. **Self-supervised learning** enables training on massive unlabeled datasets (160,000 hours of music)

5. **Temporal coherence matters**: Chunking and averaging destroys musical structure

6. **Embeddings capture audio similarity**, not social/network similarity (different from collaborative filtering)

7. **Computational trade-offs**: Full-context processing requires GPU, but provides significantly better results

8. **Real-world ML**: Sometimes the problem is infrastructure (memory limits forcing chunking), not the model

---

## Further Reading

### Papers
- **MERT**: "MERT: Acoustic Music Understanding Model with Large-Scale Self-supervised Training" (Li et al., 2023)
- **Transformers**: "Attention Is All You Need" (Vaswani et al., 2017)
- **BERT** (similar self-supervised approach for text): "BERT: Pre-training of Deep Bidirectional Transformers" (Devlin et al., 2018)

### Code
- **MERT HuggingFace**: https://huggingface.co/m-a-p/MERT-v1-95M
- **This Project**: `/embeddings_experiments/scripts/spike_6_mert_hf.py`

### Related Concepts
- **Attention Mechanism**: How models "focus" on relevant parts of input
- **Positional Encoding**: How transformers know sequence order
- **Vector Quantization**: Converting continuous to discrete representations
- **Cosine Similarity**: Measuring vector similarity by angle

---

## Hands-On Exercise

Try this to understand embeddings:

```python
# Load MERT model
from transformers import AutoModel
import torch

model = AutoModel.from_pretrained("m-a-p/MERT-v1-95M", trust_remote_code=True)

# Load two songs
audio_1 = load_audio("song1.mp3")
audio_2 = load_audio("song2.mp3")

# Extract Layer 11 embeddings
with torch.no_grad():
    output_1 = model(audio_1, output_hidden_states=True)
    output_2 = model(audio_2, output_hidden_states=True)

    layer_11_emb_1 = output_1.hidden_states[11].mean(dim=1)  # Average over time
    layer_11_emb_2 = output_2.hidden_states[11].mean(dim=1)

# Compute similarity
from sklearn.metrics.pairwise import cosine_similarity
similarity = cosine_similarity(
    layer_11_emb_1.numpy(),
    layer_11_emb_2.numpy()
)[0][0]

print(f"Similarity: {similarity:.3f}")
```

Try with:
- Two songs by the same artist (expect high similarity ~0.8-0.9)
- Two songs from the same genre (expect medium ~0.6-0.8)
- Two songs from very different genres (expect low ~0.4-0.6)

---

**Document Version**: 1.0
**Date**: 2025-11-20
**Based on**: Spike 6 Results (embeddings_experiments/docs/SPIKE_6_RESULTS.md)
**Target Level**: CS 200 (assumes CS 100 neural networks background)
