"""Route supported video source inputs to their adapters."""

from tubewatch.exceptions import InvalidSourceError
from tubewatch.models import VideoItem
from tubewatch.youtube.channel import fetch_channel_videos
from tubewatch.youtube.playlist import fetch_playlist_videos, is_playlist_url


def fetch_source_videos(source_url: str, limit: int = 10) -> list[VideoItem]:
    """Return videos from a supported channel or playlist source."""

    if not isinstance(source_url, str) or not source_url.strip():
        raise InvalidSourceError("source_url 不能为空。")
    if is_playlist_url(source_url):
        return fetch_playlist_videos(source_url, limit=limit)
    return fetch_channel_videos(source_url, limit=limit)
