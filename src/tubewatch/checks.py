"""Stateful checks for video sources."""

from datetime import UTC, datetime
from pathlib import Path

from tubewatch.models import CheckResult
from tubewatch.state import record_discovered_videos
from tubewatch.youtube.channel import fetch_channel_videos, normalize_channel_url


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
