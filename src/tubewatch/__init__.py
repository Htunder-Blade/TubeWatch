"""Public API for TubeWatch."""

from tubewatch.cleanup import cleanup_test_videos
from tubewatch.checks import (
    check_channel_updates,
    check_playlist_updates,
    check_source_updates,
)
from tubewatch.models import (
    CheckResult,
    CleanupResult,
    PlaylistItem,
    ProcessingBatchResult,
    ProcessingItemResult,
    TranscriptRecord,
    VideoItem,
)
from tubewatch.exceptions import AmbiguousTranscriptError
from tubewatch.integrations.tubescribe import TubeScribeResult
from tubewatch.processing import process_pending_videos
from tubewatch.sources import fetch_source_videos
from tubewatch.state import initialize_state_database, record_discovered_videos
from tubewatch.storage.transcripts import (
    delete_transcript,
    export_transcript_text,
    get_transcript,
    list_transcripts_for_video,
    save_transcript,
)
from tubewatch.youtube.channel import fetch_channel_playlists, fetch_channel_videos
from tubewatch.youtube.playlist import fetch_playlist_videos

__all__ = [
    "CheckResult",
    "AmbiguousTranscriptError",
    "CleanupResult",
    "PlaylistItem",
    "ProcessingBatchResult",
    "ProcessingItemResult",
    "TranscriptRecord",
    "TubeScribeResult",
    "VideoItem",
    "check_channel_updates",
    "check_playlist_updates",
    "check_source_updates",
    "cleanup_test_videos",
    "fetch_channel_playlists",
    "fetch_channel_videos",
    "fetch_playlist_videos",
    "fetch_source_videos",
    "get_transcript",
    "initialize_state_database",
    "list_transcripts_for_video",
    "process_pending_videos",
    "record_discovered_videos",
    "save_transcript",
    "delete_transcript",
    "export_transcript_text",
]
