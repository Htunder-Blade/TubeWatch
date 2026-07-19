"""Stable data models exposed by TubeWatch."""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path


@dataclass(frozen=True, slots=True)
class VideoItem:
    """Metadata for one video discovered from a video source."""

    video_id: str
    title: str
    url: str
    published_at: datetime | None
    channel_id: str | None
    channel_name: str | None


@dataclass(frozen=True, slots=True)
class PlaylistItem:
    """Metadata for one playlist exposed by a YouTube channel."""

    playlist_id: str
    title: str
    url: str


@dataclass(frozen=True, slots=True)
class CheckResult:
    """Result of one successful stateful source check."""

    source_url: str
    checked_at: datetime
    fetched_count: int
    new_videos: list[VideoItem] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class ProcessingItemResult:
    """Outcome of one TubeScribe processing attempt."""

    source_url: str
    video_id: str
    title: str
    status: str
    attempted_at: datetime
    raw_path: Path | None = None
    cleaned_path: Path | None = None
    language_code: str | None = None
    is_automatic: bool | None = None
    error_message: str | None = None


@dataclass(frozen=True, slots=True)
class ProcessingBatchResult:
    """Results from one explicit batch of pending videos."""

    attempted_count: int
    pending_remaining: int
    results: list[ProcessingItemResult] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class CleanupResult:
    """Result of deleting an exact set of tester discovery records."""

    source_url: str
    requested_count: int
    removed_count: int
    source_removed: bool
