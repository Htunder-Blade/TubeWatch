"""YouTube source adapters."""

from tubewatch.youtube.channel import fetch_channel_playlists, fetch_channel_videos
from tubewatch.youtube.playlist import fetch_playlist_videos

__all__ = [
    "fetch_channel_playlists",
    "fetch_channel_videos",
    "fetch_playlist_videos",
]
