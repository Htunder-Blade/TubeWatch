"""Read videos from a public YouTube playlist."""

from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse

from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError

from tubewatch.exceptions import InvalidSourceError, SourceFetchError
from tubewatch.models import VideoItem
from tubewatch.youtube._video import optional_text, video_item_from_entry

_YOUTUBE_HOSTS = {"youtube.com", "www.youtube.com", "m.youtube.com"}
_MIN_ENTRY_BATCH_SIZE = 20


def fetch_playlist_videos(playlist_url: str, limit: int = 10) -> list[VideoItem]:
    """Return up to ``limit`` videos from a public YouTube playlist."""

    normalized_url = normalize_playlist_url(playlist_url)
    if isinstance(limit, bool) or not isinstance(limit, int) or limit <= 0:
        raise InvalidSourceError("limit 必须是正整数。")

    videos: list[VideoItem] = []
    seen_video_ids: set[str] = set()
    batch_size = max(limit, _MIN_ENTRY_BATCH_SIZE)
    batch_start = 1

    while len(videos) < limit:
        batch_end = batch_start + batch_size - 1
        result = _extract_playlist_batch(normalized_url, batch_start, batch_end)
        entries = result.get("entries")
        if not isinstance(entries, list):
            raise SourceFetchError("该 URL 未返回播放列表视频列表。")

        channel_id = optional_text(result.get("channel_id") or result.get("uploader_id"))
        channel_name = optional_text(result.get("channel") or result.get("uploader"))
        for entry in entries:
            item = video_item_from_entry(entry, channel_id, channel_name)
            if item is None or item.video_id in seen_video_ids:
                continue
            seen_video_ids.add(item.video_id)
            videos.append(item)
            if len(videos) == limit:
                break

        playlist_count = result.get("playlist_count")
        known_count = (
            playlist_count
            if isinstance(playlist_count, int) and not isinstance(playlist_count, bool)
            else None
        )
        if not entries or (known_count is not None and batch_end >= known_count):
            break
        if known_count is None and len(entries) < batch_size:
            break
        batch_start = batch_end + 1

    return videos


def _extract_playlist_batch(
    normalized_url: str,
    batch_start: int,
    batch_end: int,
) -> dict[str, Any]:
    options: dict[str, Any] = {
        "extract_flat": True,
        "playlist_items": f"{batch_start}:{batch_end}",
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
            "无法读取该 YouTube 播放列表。请检查 URL、网络连接以及播放列表是否公开可访问。"
        ) from exc
    except Exception as exc:  # Keep third-party implementation errors private.
        raise SourceFetchError("读取 YouTube 播放列表时发生了意外错误。") from exc

    if not isinstance(result, dict):
        raise SourceFetchError("YouTube 未返回可识别的播放列表数据。")
    return result


def is_playlist_url(source_url: object) -> bool:
    """Return whether a value has the shape of a YouTube playlist URL."""

    if not isinstance(source_url, str) or not source_url.strip():
        return False
    parsed = urlparse(source_url.strip())
    return (
        parsed.scheme in {"http", "https"}
        and (parsed.hostname or "").lower() in _YOUTUBE_HOSTS
        and parsed.path.rstrip("/") == "/playlist"
    )


def normalize_playlist_url(playlist_url: str) -> str:
    """Validate and normalize a supported YouTube playlist URL."""

    if not isinstance(playlist_url, str) or not playlist_url.strip():
        raise InvalidSourceError("playlist_url 不能为空。")

    value = playlist_url.strip()
    parsed = urlparse(value)
    if (
        parsed.scheme not in {"http", "https"}
        or (parsed.hostname or "").lower() not in _YOUTUBE_HOSTS
        or parsed.path.rstrip("/") != "/playlist"
    ):
        raise InvalidSourceError(
            "请提供完整的 YouTube 播放列表 URL（/playlist?list=...）。"
        )

    playlist_ids = parse_qs(parsed.query, keep_blank_values=True).get("list", [])
    if len(playlist_ids) != 1:
        raise InvalidSourceError("YouTube 播放列表 URL 必须包含一个有效的 list 参数。")
    playlist_id = playlist_ids[0].strip()
    if not playlist_id or any(character.isspace() for character in playlist_id):
        raise InvalidSourceError("YouTube 播放列表 URL 必须包含一个有效的 list 参数。")

    return f"https://www.youtube.com/playlist?{urlencode({'list': playlist_id})}"
