"""Explicit processing workflow for discovered videos."""

from datetime import UTC, datetime
from pathlib import Path

from tubewatch.exceptions import (
    InvalidProcessingOptionError,
    TubeScribeNoSubtitlesError,
    TubeScribeProcessingError,
)
from tubewatch.integrations.tubescribe import (
    ensure_tubescribe_available,
    process_video_with_tubescribe,
)
from tubewatch.models import ProcessingBatchResult, ProcessingItemResult
from tubewatch.state import (
    count_pending_videos,
    load_pending_videos,
    mark_processing_failed,
    mark_processing_no_subtitles,
    mark_processing_succeeded,
)


def process_pending_videos(
    state_path: str | Path = Path("data/tubewatch.sqlite3"),
    raw_directory: str | Path = Path("output/raw"),
    cleaned_directory: str | Path = Path("output/cleaned"),
    limit: int = 1,
) -> ProcessingBatchResult:
    """Process up to ``limit`` pending videos through TubeScribe."""

    if isinstance(limit, bool) or not isinstance(limit, int) or limit <= 0:
        raise InvalidProcessingOptionError("limit 必须是正整数。")

    pending = load_pending_videos(state_path, limit=limit)
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
        pending_remaining=count_pending_videos(state_path),
        results=results,
    )
