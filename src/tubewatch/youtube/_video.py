"""Convert yt-dlp video entries into TubeWatch models."""

from datetime import UTC, datetime
from typing import Any

from tubewatch.models import VideoItem


def video_item_from_entry(
    entry: object,
    fallback_channel_id: str | None,
    fallback_channel_name: str | None,
) -> VideoItem | None:
    """Convert one flat yt-dlp entry into a stable ``VideoItem``."""

    if not isinstance(entry, dict):
        return None
    video_id = optional_text(entry.get("id"))
    title = optional_text(entry.get("title"))
    if not video_id or not title:
        return None

    return VideoItem(
        video_id=video_id,
        title=title,
        url=f"https://www.youtube.com/watch?v={video_id}",
        published_at=_published_at(entry),
        channel_id=optional_text(entry.get("channel_id") or entry.get("uploader_id"))
        or fallback_channel_id,
        channel_name=optional_text(entry.get("channel") or entry.get("uploader"))
        or fallback_channel_name,
    )


def optional_text(value: object) -> str | None:
    """Return a stripped non-empty string or ``None``."""

    return value.strip() if isinstance(value, str) and value.strip() else None


def _published_at(entry: dict[str, Any]) -> datetime | None:
    timestamp = entry.get("timestamp") or entry.get("release_timestamp")
    if isinstance(timestamp, (int, float)):
        return datetime.fromtimestamp(timestamp, tz=UTC)

    upload_date = entry.get("upload_date")
    if isinstance(upload_date, str):
        try:
            return datetime.strptime(upload_date, "%Y%m%d").replace(tzinfo=UTC)
        except ValueError:
            return None
    return None
