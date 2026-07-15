"""Public API for TubeWatch."""

from tubewatch.checks import (
    check_channel_updates,
    check_playlist_updates,
    check_source_updates,
)
from tubewatch.models import (
    CheckResult,
    ProcessingBatchResult,
    ProcessingItemResult,
    VideoItem,
)
from tubewatch.processing import process_pending_videos
from tubewatch.sources import fetch_source_videos
from tubewatch.youtube.channel import fetch_channel_videos
from tubewatch.youtube.playlist import fetch_playlist_videos

__all__ = [
    "CheckResult",
    "ProcessingBatchResult",
    "ProcessingItemResult",
    "VideoItem",
    "check_channel_updates",
    "check_playlist_updates",
    "check_source_updates",
    "fetch_channel_videos",
    "fetch_playlist_videos",
    "fetch_source_videos",
    "process_pending_videos",
]
