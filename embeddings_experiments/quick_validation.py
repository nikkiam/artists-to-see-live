#!/usr/bin/env python3
"""Quick validation of embeddings with the 8 artists we have."""

import json
from pathlib import Path

import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

# Load embeddings
emb_path = Path(__file__).parent / "data" / "spike_embeddings.json"
with open(emb_path) as f:
    embeddings_data = json.load(f)

# Load music-map data
music_map_path = Path(__file__).parent.parent / "output" / "similar_artists_map.json"
with open(music_map_path) as f:
    music_map = json.load(f)

artists = list(embeddings_data.keys())
embeddings = np.array([embeddings_data[a]["embedding"] for a in artists])

# Compute pairwise similarities
print(f"\n{'=' * 80}")
print(f"EMBEDDINGS VALIDATION - {len(artists)} Artists")
print(f"{'=' * 80}\n")

print("Pairwise Cosine Similarities:\n")
for i, artist1 in enumerate(artists):
    for j, artist2 in enumerate(artists[i + 1 :], start=i + 1):
        emb1 = embeddings[i].reshape(1, -1)
        emb2 = embeddings[j].reshape(1, -1)
        sim = cosine_similarity(emb1, emb2)[0][0]
        print(f"  {artist1:20s} <-> {artist2:20s}: {sim:.3f}")

print(f"\n{'=' * 80}")
print("Music-Map Comparison:")
print(f"{'=' * 80}\n")

# For each artist, see if any of our 8 artists appear in their music-map similar list
for artist in artists:
    if artist in music_map and music_map[artist].get("status") == "success":
        similar = [sa["name"] for sa in music_map[artist]["similar_artists"][:20]]
        matches = [a for a in artists if a != artist and a in similar]
        if matches:
            print(f"{artist}:")
            print(f"  Music-map similar artists in our set: {matches}")
        else:
            print(f"{artist}: No overlap with music-map top-20")
    else:
        print(f"{artist}: Not in music-map database")

print()
