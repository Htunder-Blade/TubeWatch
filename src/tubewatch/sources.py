"""Route supported video source inputs to their adapters."""

from tubewatch.exceptions import InvalidSourceError
from tubewatch.models import VideoItem
from tubewatch.youtube.channel import fetch_channel_videos, normalize_channel_url
from tubewatch.youtube.playlist import (
    fetch_playlist_videos,
    is_playlist_url,
    normalize_playlist_url,
)


def fetch_source_videos(source_url: str, limit: int = 10) -> list[VideoItem]:
    """Return videos from a supported channel or playlist source."""

    if not isinstance(source_url, str) or not source_url.strip():
        raise InvalidSourceError("source_url 不能为空。")
    if is_playlist_url(source_url):
        return fetch_playlist_videos(source_url, limit=limit)
    return fetch_channel_videos(source_url, limit=limit)


def normalize_source(source_url: str) -> tuple[str, str]:
    """Return the source type and normalized URL for a supported source."""

    if not isinstance(source_url, str) or not source_url.strip():
        raise InvalidSourceError("source_url 不能为空。")
    if is_playlist_url(source_url):
        return "playlist", normalize_playlist_url(source_url)
    return "channel", normalize_channel_url(source_url)
