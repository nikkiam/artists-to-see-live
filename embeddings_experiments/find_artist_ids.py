#!/usr/bin/env python3
"""Quick script to find correct Spotify artist IDs for ambiguous names."""

import json
from pathlib import Path

import spotipy
from spotipy.oauth2 import SpotifyClientCredentials


def load_spotify_client():
    """Load Spotify client."""
    config_path = Path(__file__).parent.parent / "spotify-config.json"
    with open(config_path, encoding="utf-8") as f:
        config = json.load(f)

    auth_manager = SpotifyClientCredentials(
        client_id=config["clientId"],
        client_secret=config["clientSecret"]
    )
    return spotipy.Spotify(auth_manager=auth_manager)


def search_artist_candidates(spotify, artist_name, limit=10):
    """Search for artist and show candidates."""
    results = spotify.search(q=f'artist:"{artist_name}"', type='artist', limit=limit)

    candidates = []
    for artist in results['artists']['items']:
        candidates.append({
            'name': artist['name'],
            'id': artist['id'],
            'genres': artist['genres'],
            'popularity': artist['popularity'],
            'followers': artist['followers']['total']
        })

    return candidates


if __name__ == "__main__":
    spotify = load_spotify_client()

    # Search for Vril
    print("=" * 80)
    print("Searching for: Vril (minimal techno)")
    print("=" * 80)
    vril_candidates = search_artist_candidates(spotify, "Vril", limit=10)
    for i, artist in enumerate(vril_candidates, 1):
        print(f"\n{i}. {artist['name']} (ID: {artist['id']})")
        print(f"   Genres: {', '.join(artist['genres']) if artist['genres'] else 'None'}")
        print(f"   Popularity: {artist['popularity']}, Followers: {artist['followers']:,}")

    # Search for Calibre
    print("\n" + "=" * 80)
    print("Searching for: Calibre (liquid drum & bass)")
    print("=" * 80)
    calibre_candidates = search_artist_candidates(spotify, "Calibre", limit=10)
    for i, artist in enumerate(calibre_candidates, 1):
        print(f"\n{i}. {artist['name']} (ID: {artist['id']})")
        print(f"   Genres: {', '.join(artist['genres']) if artist['genres'] else 'None'}")
        print(f"   Popularity: {artist['popularity']}, Followers: {artist['followers']:,}")
