"""Read recent videos from a public YouTube channel."""

from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlparse

from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError

from tubewatch.exceptions import InvalidSourceError, SourceFetchError
from tubewatch.models import VideoItem


def fetch_channel_videos(channel_url: str, limit: int = 10) -> list[VideoItem]:
    """Return up to ``limit`` recent videos from a public YouTube channel."""

    normalized_url = normalize_channel_url(channel_url)
    if isinstance(limit, bool) or not isinstance(limit, int) or limit <= 0:
        raise InvalidSourceError("limit 必须是正整数。")

    options: dict[str, Any] = {
        "extract_flat": True,
        "playlistend": limit,
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "noplaylist": False,
    }

    try:
        with YoutubeDL(options) as downloader:
            result = downloader.extract_info(normalized_url, download=False)
    except (DownloadError, OSError) as exc:
        raise SourceFetchError(
            "无法读取该 YouTube 频道。请检查 URL、网络连接以及频道是否公开可访问。"
        ) from exc
    except Exception as exc:  # Keep third-party implementation errors private.
        raise SourceFetchError("读取 YouTube 频道时发生了意外错误。") from exc

    if not isinstance(result, dict):
        raise SourceFetchError("YouTube 未返回可识别的频道数据。")

    entries = result.get("entries")
    if not isinstance(entries, list):
        raise SourceFetchError("该 URL 未返回频道视频列表。")

    channel_id = _optional_text(result.get("channel_id") or result.get("uploader_id"))
    channel_name = _optional_text(result.get("channel") or result.get("uploader"))
    videos: list[VideoItem] = []
    for entry in entries[:limit]:
        item = _to_video_item(entry, channel_id, channel_name)
        if item is not None:
            videos.append(item)
    return videos


def normalize_channel_url(channel_url: str) -> str:
    """Validate and normalize a supported YouTube channel URL."""

    if not isinstance(channel_url, str) or not channel_url.strip():
        raise InvalidSourceError("channel_url 不能为空。")

    value = channel_url.strip()
    parsed = urlparse(value)
    host = (parsed.hostname or "").lower()
    if parsed.scheme not in {"http", "https"} or host not in {
        "youtube.com",
        "www.youtube.com",
        "m.youtube.com",
    }:
        raise InvalidSourceError("请提供完整的 YouTube 频道 URL。")

    parts = [part for part in parsed.path.split("/") if part]
    is_handle = bool(parts and parts[0].startswith("@"))
    is_named_channel = len(parts) >= 2 and parts[0] in {"channel", "c", "user"}
    if not (is_handle or is_named_channel):
        raise InvalidSourceError(
            "当前仅支持 YouTube 频道主页 URL（/@handle、/channel/...、/c/... 或 /user/...）。"
        )

    # The videos tab avoids mixing Shorts/live tabs into this first-stage workflow.
    base_parts = parts[:1] if is_handle else parts[:2]
    return f"https://www.youtube.com/{'/'.join(base_parts)}/videos"


def _to_video_item(
    entry: object,
    fallback_channel_id: str | None,
    fallback_channel_name: str | None,
) -> VideoItem | None:
    if not isinstance(entry, dict):
        return None
    video_id = _optional_text(entry.get("id"))
    title = _optional_text(entry.get("title"))
    if not video_id or not title:
        return None

    return VideoItem(
        video_id=video_id,
        title=title,
        url=f"https://www.youtube.com/watch?v={video_id}",
        published_at=_published_at(entry),
        channel_id=_optional_text(entry.get("channel_id") or entry.get("uploader_id"))
        or fallback_channel_id,
        channel_name=_optional_text(entry.get("channel") or entry.get("uploader"))
        or fallback_channel_name,
    )


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


def _optional_text(value: object) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None
