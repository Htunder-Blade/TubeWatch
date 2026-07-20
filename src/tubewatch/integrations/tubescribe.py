"""Small boundary around the installed TubeScribe Python package."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from tubewatch.exceptions import (
    TubeScribeMembersOnlyError,
    TubeScribeNoSubtitlesError,
    TubeScribeProcessingError,
    TubeScribeUnavailableError,
)

_NO_SUBTITLES_MESSAGE = "该视频没有可下载的字幕。"


@dataclass(frozen=True, slots=True)
class TubeScribeResult:
    """TubeScribe fields needed by TubeWatch."""

    video_id: str
    raw_path: Path
    cleaned_path: Path
    language_code: str
    is_automatic: bool


def ensure_tubescribe_available() -> None:
    """Raise a clear error when the optional TubeScribe package is unavailable."""

    _load_workflow_api()


def process_video_with_tubescribe(
    video_url: str,
    *,
    raw_directory: str | Path,
    cleaned_directory: str | Path,
) -> TubeScribeResult:
    """Process one video through the installed TubeScribe public workflow."""

    process_video, members_only_error = _load_workflow_api()
    try:
        result = process_video(
            video_url,
            raw_directory=raw_directory,
            cleaned_directory=cleaned_directory,
            reuse_existing=False,
        )
    except members_only_error as exc:
        raise TubeScribeMembersOnlyError(str(exc)) from exc
    except Exception as exc:
        if _is_no_subtitles_error(exc):
            raise TubeScribeNoSubtitlesError(_NO_SUBTITLES_MESSAGE) from exc
        raise TubeScribeProcessingError(str(exc) or "TubeScribe 处理视频失败。") from exc

    try:
        return TubeScribeResult(
            video_id=str(result.video_id),
            raw_path=Path(result.raw_path),
            cleaned_path=Path(result.cleaned_path),
            language_code=str(result.language_code),
            is_automatic=bool(result.is_automatic),
        )
    except (AttributeError, TypeError, ValueError) as exc:
        raise TubeScribeProcessingError("TubeScribe 返回了无法识别的处理结果。") from exc


def _load_workflow_api() -> tuple[Callable[..., Any], type[Exception]]:
    try:
        from tubescribe.workflow import WorkflowMembersOnlyError, process_video
    except (ImportError, ModuleNotFoundError) as exc:
        raise TubeScribeUnavailableError(
            "TubeScribe is not installed. Install TubeWatch with the TubeScribe "
            "integration dependency or install TubeScribe separately."
        ) from exc
    return process_video, WorkflowMembersOnlyError


def _is_no_subtitles_error(error: BaseException) -> bool:
    current: BaseException | None = error
    while current is not None:
        if str(current).strip() == _NO_SUBTITLES_MESSAGE:
            return True
        current = current.__cause__ or current.__context__
    return False
