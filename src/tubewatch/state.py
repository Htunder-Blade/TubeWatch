"""SQLite persistence for discovered videos."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from tubewatch.exceptions import StateStorageError
from tubewatch.models import VideoItem


@dataclass(frozen=True, slots=True)
class PendingVideoRecord:
    """One discovered video waiting for explicit processing."""

    source_type: str
    source_url: str
    video: VideoItem


def initialize_state_database(state_path: str | Path) -> Path:
    """Create an empty TubeWatch SQLite database and return its resolved path."""

    database_path = _resolve_database_path(state_path)
    connection: sqlite3.Connection | None = None
    try:
        database_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(database_path)
        with connection:
            _create_schema(connection)
            _backfill_processing_records(connection)
        return database_path
    except (OSError, sqlite3.Error) as exc:
        raise StateStorageError(f"无法初始化 TubeWatch 状态数据库：{database_path}（{exc}）") from exc
    finally:
        if connection is not None:
            connection.close()


def record_discovered_videos(
    state_path: str | Path,
    *,
    source_type: str,
    source_url: str,
    videos: list[VideoItem],
    checked_at: datetime,
) -> list[VideoItem]:
    """Persist a successful check and return videos not previously discovered."""

    database_path = _resolve_database_path(state_path)
    connection: sqlite3.Connection | None = None
    try:
        database_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(database_path)
        connection.execute("PRAGMA foreign_keys = ON")
        with connection:
            _create_schema(connection)
            new_videos = _upsert_videos(
                connection,
                source_type=source_type,
                source_url=source_url,
                videos=videos,
                checked_at=checked_at,
            )
            _backfill_processing_records(connection)
        return new_videos
    except (OSError, sqlite3.Error) as exc:
        raise StateStorageError(f"无法更新 TubeWatch 状态数据库：{database_path}（{exc}）") from exc
    finally:
        if connection is not None:
            connection.close()


def delete_discovered_videos(
    state_path: str | Path,
    *,
    source_type: str,
    source_url: str,
    video_ids: tuple[str, ...],
) -> tuple[int, bool]:
    """Delete exact discovery records and remove their source when empty."""

    database_path = initialize_state_database(state_path)
    placeholders = ", ".join("?" for _ in video_ids)
    connection: sqlite3.Connection | None = None
    try:
        connection = sqlite3.connect(database_path)
        connection.execute("PRAGMA foreign_keys = ON")
        with connection:
            cursor = connection.execute(
                f"""
                DELETE FROM discovered_videos
                WHERE source_type = ? AND source_url = ?
                  AND video_id IN ({placeholders})
                """,
                (source_type, source_url, *video_ids),
            )
            remaining = connection.execute(
                """
                SELECT 1 FROM discovered_videos
                WHERE source_type = ? AND source_url = ?
                LIMIT 1
                """,
                (source_type, source_url),
            ).fetchone()
            source_removed = False
            if remaining is None:
                source_cursor = connection.execute(
                    "DELETE FROM sources WHERE source_type = ? AND source_url = ?",
                    (source_type, source_url),
                )
                source_removed = source_cursor.rowcount == 1
        return cursor.rowcount, source_removed
    except (OSError, sqlite3.Error) as exc:
        raise StateStorageError(f"无法清理测试发现记录：{database_path}（{exc}）") from exc
    finally:
        if connection is not None:
            connection.close()


def _resolve_database_path(state_path: str | Path) -> Path:
    try:
        path = Path(state_path).expanduser().resolve()
    except (OSError, TypeError, ValueError) as exc:
        raise StateStorageError(f"无法解析状态数据库路径：{state_path}（{exc}）") from exc
    if path.exists() and path.is_dir():
        raise StateStorageError(f"状态数据库路径不能是目录：{path}")
    return path


def _create_schema(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS sources (
            source_type TEXT NOT NULL,
            source_url TEXT NOT NULL,
            last_checked_at TEXT NOT NULL,
            PRIMARY KEY (source_type, source_url)
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS discovered_videos (
            source_type TEXT NOT NULL,
            source_url TEXT NOT NULL,
            video_id TEXT NOT NULL,
            title TEXT NOT NULL,
            url TEXT NOT NULL,
            published_at TEXT,
            channel_id TEXT,
            channel_name TEXT,
            first_seen_at TEXT NOT NULL,
            last_seen_at TEXT NOT NULL,
            PRIMARY KEY (source_type, source_url, video_id),
            FOREIGN KEY (source_type, source_url)
                REFERENCES sources (source_type, source_url)
                ON DELETE CASCADE
        )
        """
    )
    _ensure_processing_records_schema(connection)


def _ensure_processing_records_schema(connection: sqlite3.Connection) -> None:
    row = connection.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'processing_records'"
    ).fetchone()
    if row is None:
        _create_processing_records_table(connection)
        return
    if "'no_subtitles'" in row[0]:
        return

    connection.execute(
        "ALTER TABLE processing_records RENAME TO processing_records_legacy"
    )
    _create_processing_records_table(connection)
    connection.execute(
        """
        INSERT INTO processing_records (
            source_type, source_url, video_id, status, attempt_count,
            last_attempt_at, raw_path, cleaned_path, language_code,
            is_automatic, error_message
        )
        SELECT
            source_type, source_url, video_id,
            CASE
                WHEN status = 'failed' AND error_message = ? THEN 'no_subtitles'
                ELSE status
            END,
            attempt_count, last_attempt_at, raw_path, cleaned_path,
            language_code, is_automatic, error_message
        FROM processing_records_legacy
        """,
        ("该视频没有可下载的字幕。",),
    )
    connection.execute("DROP TABLE processing_records_legacy")


def _create_processing_records_table(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE processing_records (
            source_type TEXT NOT NULL,
            source_url TEXT NOT NULL,
            video_id TEXT NOT NULL,
            status TEXT NOT NULL CHECK (
                status IN ('pending', 'succeeded', 'failed', 'no_subtitles')
            ),
            attempt_count INTEGER NOT NULL DEFAULT 0,
            last_attempt_at TEXT,
            raw_path TEXT,
            cleaned_path TEXT,
            language_code TEXT,
            is_automatic INTEGER,
            error_message TEXT,
            PRIMARY KEY (source_type, source_url, video_id),
            FOREIGN KEY (source_type, source_url, video_id)
                REFERENCES discovered_videos (source_type, source_url, video_id)
                ON DELETE CASCADE
        )
        """
    )


def _upsert_videos(
    connection: sqlite3.Connection,
    *,
    source_type: str,
    source_url: str,
    videos: list[VideoItem],
    checked_at: datetime,
) -> list[VideoItem]:
    checked_at_text = checked_at.isoformat()
    connection.execute(
        """
        INSERT INTO sources (source_type, source_url, last_checked_at)
        VALUES (?, ?, ?)
        ON CONFLICT (source_type, source_url)
        DO UPDATE SET last_checked_at = excluded.last_checked_at
        """,
        (source_type, source_url, checked_at_text),
    )

    new_videos: list[VideoItem] = []
    for video in videos:
        existing = connection.execute(
            """
            SELECT 1 FROM discovered_videos
            WHERE source_type = ? AND source_url = ? AND video_id = ?
            """,
            (source_type, source_url, video.video_id),
        ).fetchone()
        if existing is None:
            new_videos.append(video)

        connection.execute(
            """
            INSERT INTO discovered_videos (
                source_type, source_url, video_id, title, url, published_at,
                channel_id, channel_name, first_seen_at, last_seen_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (source_type, source_url, video_id) DO UPDATE SET
                title = excluded.title,
                url = excluded.url,
                published_at = excluded.published_at,
                channel_id = excluded.channel_id,
                channel_name = excluded.channel_name,
                last_seen_at = excluded.last_seen_at
            """,
            (
                source_type,
                source_url,
                video.video_id,
                video.title,
                video.url,
                video.published_at.isoformat() if video.published_at else None,
                video.channel_id,
                video.channel_name,
                checked_at_text,
                checked_at_text,
            ),
        )
    return new_videos


def load_pending_videos(
    state_path: str | Path,
    *,
    limit: int,
    source_type: str | None = None,
    source_url: str | None = None,
    video_ids: tuple[str, ...] | None = None,
) -> list[PendingVideoRecord]:
    """Return pending videos in first-discovered order."""

    database_path = initialize_state_database(state_path)
    where_sql, parameters = _pending_filter(
        source_type=source_type,
        source_url=source_url,
        video_ids=video_ids,
    )
    connection: sqlite3.Connection | None = None
    try:
        connection = sqlite3.connect(database_path)
        rows = connection.execute(
            """
            SELECT
                d.source_type, d.source_url, d.video_id, d.title, d.url,
                d.published_at, d.channel_id, d.channel_name
            FROM discovered_videos AS d
            JOIN processing_records AS p
              ON p.source_type = d.source_type
             AND p.source_url = d.source_url
             AND p.video_id = d.video_id
            WHERE {where_sql}
            ORDER BY d.first_seen_at, d.rowid
            LIMIT ?
            """.format(where_sql=where_sql),
            (*parameters, limit),
        ).fetchall()
        return [
            PendingVideoRecord(
                source_type=row[0],
                source_url=row[1],
                video=VideoItem(
                    video_id=row[2],
                    title=row[3],
                    url=row[4],
                    published_at=datetime.fromisoformat(row[5]) if row[5] else None,
                    channel_id=row[6],
                    channel_name=row[7],
                ),
            )
            for row in rows
        ]
    except (OSError, sqlite3.Error, ValueError) as exc:
        raise StateStorageError(f"无法读取待处理视频：{database_path}（{exc}）") from exc
    finally:
        if connection is not None:
            connection.close()


def mark_processing_succeeded(
    state_path: str | Path,
    record: PendingVideoRecord,
    *,
    attempted_at: datetime,
    raw_path: Path,
    cleaned_path: Path,
    language_code: str,
    is_automatic: bool,
) -> None:
    """Record one successful TubeScribe attempt."""

    _update_processing_record(
        state_path,
        record,
        status="succeeded",
        attempted_at=attempted_at,
        raw_path=str(raw_path),
        cleaned_path=str(cleaned_path),
        language_code=language_code,
        is_automatic=int(is_automatic),
        error_message=None,
    )


def mark_processing_failed(
    state_path: str | Path,
    record: PendingVideoRecord,
    *,
    attempted_at: datetime,
    error_message: str,
) -> None:
    """Record one failed TubeScribe attempt without retrying it."""

    _update_processing_record(
        state_path,
        record,
        status="failed",
        attempted_at=attempted_at,
        raw_path=None,
        cleaned_path=None,
        language_code=None,
        is_automatic=None,
        error_message=error_message,
    )


def mark_processing_no_subtitles(
    state_path: str | Path,
    record: PendingVideoRecord,
    *,
    attempted_at: datetime,
    error_message: str,
) -> None:
    """Record that one video has no downloadable subtitles."""

    _update_processing_record(
        state_path,
        record,
        status="no_subtitles",
        attempted_at=attempted_at,
        raw_path=None,
        cleaned_path=None,
        language_code=None,
        is_automatic=None,
        error_message=error_message,
    )


def count_pending_videos(
    state_path: str | Path,
    *,
    source_type: str | None = None,
    source_url: str | None = None,
    video_ids: tuple[str, ...] | None = None,
) -> int:
    """Return the number of videos still pending processing."""

    database_path = initialize_state_database(state_path)
    where_sql, parameters = _pending_filter(
        source_type=source_type,
        source_url=source_url,
        video_ids=video_ids,
    )
    connection: sqlite3.Connection | None = None
    try:
        connection = sqlite3.connect(database_path)
        return int(
            connection.execute(
                f"""
                SELECT COUNT(*)
                FROM discovered_videos AS d
                JOIN processing_records AS p
                  ON p.source_type = d.source_type
                 AND p.source_url = d.source_url
                 AND p.video_id = d.video_id
                WHERE {where_sql}
                """,
                parameters,
            ).fetchone()[0]
        )
    except (OSError, sqlite3.Error) as exc:
        raise StateStorageError(f"无法读取处理状态：{database_path}（{exc}）") from exc
    finally:
        if connection is not None:
            connection.close()


def _pending_filter(
    *,
    source_type: str | None,
    source_url: str | None,
    video_ids: tuple[str, ...] | None,
) -> tuple[str, tuple[object, ...]]:
    clauses = ["p.status = 'pending'"]
    parameters: list[object] = []
    if source_type is not None:
        clauses.append("d.source_type = ?")
        parameters.append(source_type)
    if source_url is not None:
        clauses.append("d.source_url = ?")
        parameters.append(source_url)
    if video_ids is not None:
        placeholders = ", ".join("?" for _ in video_ids)
        clauses.append(f"d.video_id IN ({placeholders})")
        parameters.extend(video_ids)
    return " AND ".join(clauses), tuple(parameters)


def _backfill_processing_records(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        INSERT OR IGNORE INTO processing_records (
            source_type, source_url, video_id, status
        )
        SELECT source_type, source_url, video_id, 'pending'
        FROM discovered_videos
        """
    )


def _update_processing_record(
    state_path: str | Path,
    record: PendingVideoRecord,
    *,
    status: str,
    attempted_at: datetime,
    raw_path: str | None,
    cleaned_path: str | None,
    language_code: str | None,
    is_automatic: int | None,
    error_message: str | None,
) -> None:
    database_path = _resolve_database_path(state_path)
    connection: sqlite3.Connection | None = None
    try:
        connection = sqlite3.connect(database_path)
        with connection:
            cursor = connection.execute(
                """
                UPDATE processing_records SET
                    status = ?,
                    attempt_count = attempt_count + 1,
                    last_attempt_at = ?,
                    raw_path = ?,
                    cleaned_path = ?,
                    language_code = ?,
                    is_automatic = ?,
                    error_message = ?
                WHERE source_type = ? AND source_url = ? AND video_id = ?
                """,
                (
                    status,
                    attempted_at.isoformat(),
                    raw_path,
                    cleaned_path,
                    language_code,
                    is_automatic,
                    error_message,
                    record.source_type,
                    record.source_url,
                    record.video.video_id,
                ),
            )
            if cursor.rowcount != 1:
                raise sqlite3.IntegrityError("找不到对应的待处理记录。")
    except (OSError, sqlite3.Error) as exc:
        raise StateStorageError(f"无法更新处理状态：{database_path}（{exc}）") from exc
    finally:
        if connection is not None:
            connection.close()
