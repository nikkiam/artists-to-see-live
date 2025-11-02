#!/usr/bin/env python3
"""
Script to extract unique artist names from Spotify playlists and save to JSON.
"""

import json
import requests
from pathlib import Path


def load_spotify_config():
    """Load Spotify credentials from spotify-config.json."""
    config_path = Path(__file__).parent / "spotify-config.json"
    with open(config_path, 'r') as f:
        return json.load(f)


def refresh_access_token(config):
    """Refresh the Spotify access token using the refresh token."""
    url = "https://accounts.spotify.com/api/token"
    data = {
        "grant_type": "refresh_token",
        "refresh_token": config["refreshToken"],
        "client_id": config["clientId"],
        "client_secret": config["clientSecret"]
    }

    response = requests.post(url, data=data)
    response.raise_for_status()

    token_data = response.json()
    return token_data["access_token"]


def get_playlist_tracks(playlist_id, access_token):
    """Fetch all tracks from a Spotify playlist."""
    tracks = []
    offset = 0
    limit = 50

    headers = {
        "Authorization": f"Bearer {access_token}"
    }

    while True:
        url = f"https://api.spotify.com/v1/playlists/{playlist_id}/tracks"
        params = {
            "limit": limit,
            "offset": offset,
            "fields": "items(track(artists(name))),total"
        }

        print(f"Fetching tracks from playlist {playlist_id}, offset {offset}...")
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()

        data = response.json()
        tracks.extend(data["items"])

        if len(data["items"]) < limit:
            break

        offset += limit

    return tracks


def extract_artist_names(playlist_ids, access_token):
    """Extract unique artist names from multiple playlists."""
    all_artists = set()

    for playlist_id in playlist_ids:
        tracks = get_playlist_tracks(playlist_id, access_token)

        for item in tracks:
            if item and item.get("track") and item["track"].get("artists"):
                for artist in item["track"]["artists"]:
                    if artist.get("name"):
                        all_artists.add(artist["name"])

    return sorted(list(all_artists))


def main():
    # Load Spotify credentials
    print("Loading Spotify credentials...")
    config = load_spotify_config()

    # Try to use existing access token, refresh if needed
    try:
        access_token = config["accessToken"]
    except Exception:
        print("Refreshing access token...")
        access_token = refresh_access_token(config)

    # Playlist IDs for "First Decade - Collection" and "Collection"
    playlist_ids = [
        "1xToOCtRLgteNJFNIPpdEs",  # First Decade - Collection (712 tracks)
        "1mLkKgbsqAfkmM4byW93dF",  # Collection (236 tracks)
    ]

    print("Extracting artist names from playlists...")
    try:
        artists = extract_artist_names(playlist_ids, access_token)
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 401:
            print("Access token expired, refreshing...")
            access_token = refresh_access_token(config)
            artists = extract_artist_names(playlist_ids, access_token)
        else:
            raise

    print(f"Found {len(artists)} unique artists")

    # Save to JSON file
    output_file = "my_artists.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump({"artists": artists}, f, indent=2, ensure_ascii=False)

    print(f"Artists saved to {output_file}")


if __name__ == "__main__":
    main()
