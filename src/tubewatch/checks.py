"""Stateful checks for video sources."""

from datetime import UTC, datetime
from pathlib import Path

from tubewatch.exceptions import InvalidSourceError
from tubewatch.models import CheckResult
from tubewatch.state import record_discovered_videos
from tubewatch.youtube.channel import fetch_channel_videos, normalize_channel_url
from tubewatch.youtube.playlist import (
    fetch_playlist_videos,
    is_playlist_url,
    normalize_playlist_url,
)


def check_source_updates(
    source_url: str,
    state_path: str | Path = Path("data/tubewatch.sqlite3"),
    limit: int = 10,
) -> CheckResult:
    """Check a supported channel or playlist for newly discovered videos."""

    if not isinstance(source_url, str) or not source_url.strip():
        raise InvalidSourceError("source_url 不能为空。")
    if is_playlist_url(source_url):
        return check_playlist_updates(source_url, state_path=state_path, limit=limit)
    return check_channel_updates(source_url, state_path=state_path, limit=limit)


def check_channel_updates(
    channel_url: str,
    state_path: str | Path = Path("data/tubewatch.sqlite3"),
    limit: int = 10,
) -> CheckResult:
    """Fetch a channel and return videos not discovered by earlier checks."""

    source_url = normalize_channel_url(channel_url)
    videos = fetch_channel_videos(channel_url, limit=limit)
    checked_at = datetime.now(tz=UTC)
    new_videos = record_discovered_videos(
        state_path,
        source_type="channel",
        source_url=source_url,
        videos=videos,
        checked_at=checked_at,
    )
    return CheckResult(
        source_url=source_url,
        checked_at=checked_at,
        fetched_count=len(videos),
        new_videos=new_videos,
    )


def check_playlist_updates(
    playlist_url: str,
    state_path: str | Path = Path("data/tubewatch.sqlite3"),
    limit: int = 10,
) -> CheckResult:
    """Fetch a playlist and return videos not discovered by earlier checks."""

    source_url = normalize_playlist_url(playlist_url)
    videos = fetch_playlist_videos(playlist_url, limit=limit)
    checked_at = datetime.now(tz=UTC)
    new_videos = record_discovered_videos(
        state_path,
        source_type="playlist",
        source_url=source_url,
        videos=videos,
        checked_at=checked_at,
    )
    return CheckResult(
        source_url=source_url,
        checked_at=checked_at,
        fetched_count=len(videos),
        new_videos=new_videos,
    )
