"""Explicit processing workflow for discovered videos."""

from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

from tubewatch.exceptions import (
    InvalidProcessingOptionError,
    TubeScribeMembersOnlyError,
    TubeScribeNoSubtitlesError,
    TubeScribeProcessingError,
)
from tubewatch.integrations.tubescribe import (
    ensure_tubescribe_available,
    process_video_with_tubescribe,
)
from tubewatch.models import ProcessingBatchResult, ProcessingItemResult
from tubewatch.sources import normalize_source
from tubewatch.state import (
    count_pending_videos,
    load_pending_videos,
    mark_processing_failed,
    mark_processing_members_only,
    mark_processing_no_subtitles,
    mark_processing_succeeded,
)


def process_pending_videos(
    state_path: str | Path = Path("data/tubewatch.sqlite3"),
    raw_directory: str | Path = Path("output/raw"),
    cleaned_directory: str | Path = Path("output/cleaned"),
    limit: int = 1,
    source_url: str | None = None,
    video_ids: Sequence[str] | None = None,
) -> ProcessingBatchResult:
    """Process up to ``limit`` pending videos through TubeScribe."""

    if isinstance(limit, bool) or not isinstance(limit, int) or limit <= 0:
        raise InvalidProcessingOptionError("limit 必须是正整数。")

    source_type: str | None = None
    normalized_source_url: str | None = None
    normalized_video_ids: tuple[str, ...] | None = None
    if (source_url is None) != (video_ids is None):
        raise InvalidProcessingOptionError(
            "source_url 和 video_ids 必须同时提供或同时省略。"
        )
    if source_url is not None and video_ids is not None:
        source_type, normalized_source_url = normalize_source(source_url)
        normalized_video_ids = _normalize_video_ids(video_ids)

    pending = load_pending_videos(
        state_path,
        limit=limit,
        source_type=source_type,
        source_url=normalized_source_url,
        video_ids=normalized_video_ids,
    )
    if not pending:
        return ProcessingBatchResult(attempted_count=0, pending_remaining=0)

    ensure_tubescribe_available()
    results: list[ProcessingItemResult] = []
    for record in pending:
        attempted_at = datetime.now(tz=UTC)
        try:
            integration_result = process_video_with_tubescribe(
                record.video.url,
                raw_directory=raw_directory,
                cleaned_directory=cleaned_directory,
            )
            if integration_result.video_id != record.video.video_id:
                raise TubeScribeProcessingError(
                    "TubeScribe 返回的视频 ID 与待处理记录不一致。"
                )
        except TubeScribeMembersOnlyError as exc:
            message = str(exc)
            mark_processing_members_only(
                state_path,
                record,
                attempted_at=attempted_at,
                error_message=message,
            )
            results.append(
                ProcessingItemResult(
                    source_url=record.source_url,
                    video_id=record.video.video_id,
                    title=record.video.title,
                    status="members_only",
                    attempted_at=attempted_at,
                    error_message=message,
                )
            )
            continue
        except TubeScribeNoSubtitlesError as exc:
            message = str(exc)
            mark_processing_no_subtitles(
                state_path,
                record,
                attempted_at=attempted_at,
                error_message=message,
            )
            results.append(
                ProcessingItemResult(
                    source_url=record.source_url,
                    video_id=record.video.video_id,
                    title=record.video.title,
                    status="no_subtitles",
                    attempted_at=attempted_at,
                    error_message=message,
                )
            )
            continue
        except TubeScribeProcessingError as exc:
            message = str(exc)
            mark_processing_failed(
                state_path,
                record,
                attempted_at=attempted_at,
                error_message=message,
            )
            results.append(
                ProcessingItemResult(
                    source_url=record.source_url,
                    video_id=record.video.video_id,
                    title=record.video.title,
                    status="failed",
                    attempted_at=attempted_at,
                    error_message=message,
                )
            )
            continue

        mark_processing_succeeded(
            state_path,
            record,
            attempted_at=attempted_at,
            raw_path=integration_result.raw_path,
            cleaned_path=integration_result.cleaned_path,
            language_code=integration_result.language_code,
            is_automatic=integration_result.is_automatic,
        )
        results.append(
            ProcessingItemResult(
                source_url=record.source_url,
                video_id=record.video.video_id,
                title=record.video.title,
                status="succeeded",
                attempted_at=attempted_at,
                raw_path=integration_result.raw_path,
                cleaned_path=integration_result.cleaned_path,
                language_code=integration_result.language_code,
                is_automatic=integration_result.is_automatic,
            )
        )

    return ProcessingBatchResult(
        attempted_count=len(results),
        pending_remaining=count_pending_videos(
            state_path,
            source_type=source_type,
            source_url=normalized_source_url,
            video_ids=normalized_video_ids,
        ),
        results=results,
    )


def _normalize_video_ids(video_ids: Sequence[str]) -> tuple[str, ...]:
    if isinstance(video_ids, (str, bytes)):
        raise InvalidProcessingOptionError("video_ids 必须是视频 ID 序列。")
    normalized: list[str] = []
    seen: set[str] = set()
    for video_id in video_ids:
        if not isinstance(video_id, str) or not video_id.strip():
            raise InvalidProcessingOptionError("video_ids 不能包含空的视频 ID。")
        value = video_id.strip()
        if value not in seen:
            normalized.append(value)
            seen.add(value)
    if not normalized:
        raise InvalidProcessingOptionError("video_ids 至少需要一个视频 ID。")
    return tuple(normalized)
