"""Project-level exceptions for TubeWatch."""


class TubeWatchError(Exception):
    """Base exception for expected TubeWatch failures."""


class InvalidSourceError(TubeWatchError, ValueError):
    """Raised when a video source URL or option is invalid."""


class SourceFetchError(TubeWatchError):
    """Raised when a video source cannot be read."""


class StateStorageError(TubeWatchError):
    """Raised when TubeWatch cannot read or update its local state."""


class TubeScribeUnavailableError(TubeWatchError):
    """Raised when the optional TubeScribe package is not installed."""


class TubeScribeProcessingError(TubeWatchError):
    """Raised when TubeScribe cannot process one video."""


class TubeScribeNoSubtitlesError(TubeScribeProcessingError):
    """Raised when a video has no downloadable subtitles."""


class InvalidProcessingOptionError(TubeWatchError, ValueError):
    """Raised when a processing batch option is invalid."""
