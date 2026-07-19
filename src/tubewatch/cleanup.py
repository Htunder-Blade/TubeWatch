"""Exact cleanup operations used by the end-to-end tester."""

from collections.abc import Sequence
from pathlib import Path

from tubewatch.exceptions import InvalidCleanupOptionError
from tubewatch.models import CleanupResult
from tubewatch.sources import normalize_source
from tubewatch.state import delete_discovered_videos


def cleanup_test_videos(
    source_url: str,
    video_ids: Sequence[str],
    state_path: str | Path = Path("data/tubewatch.sqlite3"),
) -> CleanupResult:
    """Delete only the specified tester discovery records."""

    normalized_video_ids = _normalize_video_ids(video_ids)
    source_type, normalized_source_url = normalize_source(source_url)
    removed_count, source_removed = delete_discovered_videos(
        state_path,
        source_type=source_type,
        source_url=normalized_source_url,
        video_ids=normalized_video_ids,
    )
    return CleanupResult(
        source_url=normalized_source_url,
        requested_count=len(normalized_video_ids),
        removed_count=removed_count,
        source_removed=source_removed,
    )


def _normalize_video_ids(video_ids: Sequence[str]) -> tuple[str, ...]:
    if isinstance(video_ids, (str, bytes)):
        raise InvalidCleanupOptionError("video_ids 必须是视频 ID 序列。")
    normalized: list[str] = []
    seen: set[str] = set()
    for video_id in video_ids:
        if not isinstance(video_id, str) or not video_id.strip():
            raise InvalidCleanupOptionError("video_ids 不能包含空的视频 ID。")
        value = video_id.strip()
        if value not in seen:
            normalized.append(value)
            seen.add(value)
    if not normalized:
        raise InvalidCleanupOptionError("video_ids 至少需要一个视频 ID。")
    return tuple(normalized)
