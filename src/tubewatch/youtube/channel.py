"""Read recent videos from a public YouTube channel."""

from typing import Any
from urllib.parse import urlencode, urlparse

from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError

from tubewatch.exceptions import InvalidSourceError, SourceFetchError
from tubewatch.models import PlaylistItem, VideoItem
from tubewatch.youtube._video import optional_text, video_item_from_entry


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

    channel_id = optional_text(result.get("channel_id") or result.get("uploader_id"))
    channel_name = optional_text(result.get("channel") or result.get("uploader"))
    videos: list[VideoItem] = []
    for entry in entries[:limit]:
        item = video_item_from_entry(entry, channel_id, channel_name)
        if item is not None:
            videos.append(item)
    return videos


def fetch_channel_playlists(channel_url: str) -> list[PlaylistItem]:
    """Return public playlists exposed on a YouTube channel's playlists tab."""

    normalized_url = _normalize_channel_tab_url(channel_url, "playlists")
    options: dict[str, Any] = {
        "extract_flat": True,
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
            "无法读取该 YouTube 频道的播放列表。请检查频道、网络连接以及播放列表是否公开可访问。"
        ) from exc
    except Exception as exc:  # Keep third-party implementation errors private.
        raise SourceFetchError("读取 YouTube 频道播放列表时发生了意外错误。") from exc

    if not isinstance(result, dict):
        raise SourceFetchError("YouTube 未返回可识别的频道播放列表数据。")
    entries = result.get("entries")
    if not isinstance(entries, list):
        raise SourceFetchError("该频道未返回可识别的播放列表清单。")

    playlists: list[PlaylistItem] = []
    seen_ids: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        playlist_id = optional_text(entry.get("id"))
        title = optional_text(entry.get("title"))
        if not playlist_id or not title or playlist_id in seen_ids:
            continue
        seen_ids.add(playlist_id)
        playlists.append(
            PlaylistItem(
                playlist_id=playlist_id,
                title=title,
                url=f"https://www.youtube.com/playlist?{urlencode({'list': playlist_id})}",
            )
        )
    return playlists


def normalize_channel_url(channel_url: str) -> str:
    """Validate and normalize a YouTube channel URL or ``@handle``."""

    return _normalize_channel_tab_url(channel_url, "videos")


def normalize_channel_playlists_url(channel_url: str) -> str:
    """Validate a channel input and normalize its playlists tab URL."""

    return _normalize_channel_tab_url(channel_url, "playlists")


def _normalize_channel_tab_url(channel_url: str, tab: str) -> str:
    """Validate a channel input and normalize one supported tab URL."""

    if not isinstance(channel_url, str) or not channel_url.strip():
        raise InvalidSourceError("channel_url 不能为空。")

    value = channel_url.strip()
    if value.startswith("@"):
        if (
            len(value) == 1
            or any(delimiter in value for delimiter in "/?#\\")
            or any(character.isspace() for character in value)
        ):
            raise InvalidSourceError("请提供有效的 YouTube 频道 handle，例如 @wangzhian。")
        return f"https://www.youtube.com/{value}/{tab}"

    parsed = urlparse(value)
    host = (parsed.hostname or "").lower()
    if parsed.scheme not in {"http", "https"} or host not in {
        "youtube.com",
        "www.youtube.com",
        "m.youtube.com",
    }:
        raise InvalidSourceError("请提供 @handle 或完整的 YouTube 频道 URL。")

    parts = [part for part in parsed.path.split("/") if part]
    is_handle = bool(parts and parts[0].startswith("@"))
    is_named_channel = len(parts) >= 2 and parts[0] in {"channel", "c", "user"}
    if not (is_handle or is_named_channel):
        raise InvalidSourceError(
            "当前仅支持 YouTube 频道主页 URL（/@handle、/channel/...、/c/... 或 /user/...）。"
        )

    base_parts = parts[:1] if is_handle else parts[:2]
    return f"https://www.youtube.com/{'/'.join(base_parts)}/{tab}"
