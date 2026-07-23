"""Shared SQLite connection and migration helpers."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Callable

from tubewatch.exceptions import StateStorageError


@dataclass(frozen=True, slots=True)
class Migration:
    """One ordered database schema migration."""

    version: int
    description: str
    apply: Callable[[sqlite3.Connection], None]


def resolve_database_path(state_path: str | Path) -> Path:
    """Return a validated absolute database path."""

    try:
        path = Path(state_path).expanduser().resolve()
    except (OSError, TypeError, ValueError) as exc:
        raise StateStorageError(f"无法解析状态数据库路径：{state_path}（{exc}）") from exc
    if path.exists() and path.is_dir():
        raise StateStorageError(f"状态数据库路径不能是目录：{path}")
    return path


def connect_database(database_path: Path) -> sqlite3.Connection:
    """Open a SQLite connection with foreign keys enabled."""

    connection = sqlite3.connect(database_path)
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def initialize_database(state_path: str | Path) -> Path:
    """Create or migrate a TubeWatch database and return its path."""

    database_path = resolve_database_path(state_path)
    connection: sqlite3.Connection | None = None
    try:
        database_path.parent.mkdir(parents=True, exist_ok=True)
        connection = connect_database(database_path)
        _apply_migrations(connection)
        return database_path
    except (OSError, sqlite3.Error) as exc:
        raise StateStorageError(
            f"无法初始化 TubeWatch 状态数据库：{database_path}（{exc}）"
        ) from exc
    finally:
        if connection is not None:
            connection.close()


def utc_text(value: datetime | None = None) -> str:
    """Return a stable UTC ISO 8601 timestamp."""

    current = value or datetime.now(tz=UTC)
    if current.tzinfo is None:
        raise ValueError("数据库时间必须包含时区。")
    return current.astimezone(UTC).isoformat(timespec="microseconds")


def _apply_migrations(connection: sqlite3.Connection) -> None:
    migrations = (
        Migration(1, "initial source and processing state", _migration_001_initial),
        Migration(2, "store cleaned transcripts in SQLite", _migration_002_transcripts),
    )
    connection.execute("BEGIN IMMEDIATE")
    try:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version INTEGER PRIMARY KEY,
                applied_at TEXT NOT NULL,
                description TEXT NOT NULL
            )
            """
        )
        applied = {
            int(row[0])
            for row in connection.execute("SELECT version FROM schema_migrations")
        }
        known_versions = {migration.version for migration in migrations}
        unknown = applied - known_versions
        if unknown:
            raise sqlite3.DatabaseError(
                f"数据库包含当前程序无法识别的 migration：{sorted(unknown)}"
            )
        for migration in migrations:
            if migration.version in applied:
                continue
            migration.apply(connection)
            connection.execute(
                """
                INSERT INTO schema_migrations (version, applied_at, description)
                VALUES (?, ?, ?)
                """,
                (migration.version, utc_text(), migration.description),
            )
        connection.commit()
    except Exception:
        connection.rollback()
        raise


def _migration_001_initial(connection: sqlite3.Connection) -> None:
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
    row = connection.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'processing_records'"
    ).fetchone()
    if row is None:
        _create_processing_records(connection)
    elif "'no_subtitles'" not in str(row[0]) or "'members_only'" not in str(row[0]):
        _upgrade_legacy_processing_records(connection)
    connection.execute(
        """
        INSERT OR IGNORE INTO processing_records (
            source_type, source_url, video_id, status
        )
        SELECT source_type, source_url, video_id, 'pending'
        FROM discovered_videos
        """
    )


def _migration_002_transcripts(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE videos (
            video_id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            url TEXT NOT NULL,
            published_at TEXT,
            channel_id TEXT,
            channel_name TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    rows = connection.execute(
        """
        SELECT video_id, title, url, published_at, channel_id, channel_name,
               first_seen_at, last_seen_at
        FROM discovered_videos
        ORDER BY first_seen_at, rowid
        """
    ).fetchall()
    for row in rows:
        connection.execute(
            """
            INSERT INTO videos (
                video_id, title, url, published_at, channel_id, channel_name,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (video_id) DO UPDATE SET
                title = excluded.title,
                url = excluded.url,
                published_at = excluded.published_at,
                channel_id = excluded.channel_id,
                channel_name = excluded.channel_name,
                created_at = MIN(videos.created_at, excluded.created_at),
                updated_at = MAX(videos.updated_at, excluded.updated_at)
            """,
            row,
        )
    connection.execute(
        """
        CREATE TABLE transcripts (
            id INTEGER PRIMARY KEY,
            video_id TEXT NOT NULL REFERENCES videos(video_id) ON DELETE CASCADE,
            language_code TEXT NOT NULL,
            source_kind TEXT NOT NULL CHECK (
                source_kind IN ('manual', 'auto_generated', 'translated', 'unknown')
            ),
            format TEXT NOT NULL DEFAULT 'plain_text'
                CHECK (format = 'plain_text'),
            cleaned_text TEXT NOT NULL,
            cleaner_name TEXT,
            cleaner_version TEXT,
            source_content_hash TEXT,
            cleaned_content_hash TEXT NOT NULL,
            character_count INTEGER NOT NULL CHECK (character_count >= 0),
            word_count INTEGER CHECK (word_count IS NULL OR word_count >= 0),
            raw_file_path TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            UNIQUE(video_id, language_code, source_kind)
        )
        """
    )
    connection.execute(
        """
        ALTER TABLE processing_records
        ADD COLUMN transcript_id INTEGER REFERENCES transcripts(id) ON DELETE SET NULL
        """
    )
    connection.execute(
        """
        UPDATE processing_records
        SET status = 'pending',
            error_message = '旧版 succeeded 记录没有权威 transcript，需要重新处理。'
        WHERE status = 'succeeded' AND transcript_id IS NULL
        """
    )
    connection.execute(
        """
        CREATE TRIGGER discovered_video_requires_global_video
        BEFORE INSERT ON discovered_videos
        WHEN NOT EXISTS (SELECT 1 FROM videos WHERE video_id = NEW.video_id)
        BEGIN
            SELECT RAISE(ABORT, 'discovered video requires a global video record');
        END
        """
    )
    connection.execute(
        """
        CREATE TRIGGER discovered_video_update_requires_global_video
        BEFORE UPDATE OF video_id ON discovered_videos
        WHEN NOT EXISTS (SELECT 1 FROM videos WHERE video_id = NEW.video_id)
        BEGIN
            SELECT RAISE(ABORT, 'discovered video requires a global video record');
        END
        """
    )
    connection.execute(
        """
        CREATE TRIGGER prevent_discovered_global_video_delete
        BEFORE DELETE ON videos
        WHEN EXISTS (SELECT 1 FROM discovered_videos WHERE video_id = OLD.video_id)
        BEGIN
            SELECT RAISE(ABORT, 'cannot delete a video that still has discoveries');
        END
        """
    )
    connection.execute(
        """
        CREATE TRIGGER processing_success_requires_transcript
        BEFORE INSERT ON processing_records
        WHEN NEW.status = 'succeeded' AND (
            NEW.transcript_id IS NULL OR NOT EXISTS (
                SELECT 1 FROM transcripts
                WHERE id = NEW.transcript_id AND video_id = NEW.video_id
            )
        )
        BEGIN
            SELECT RAISE(ABORT, 'succeeded processing record requires its video transcript');
        END
        """
    )
    connection.execute(
        """
        CREATE TRIGGER processing_success_update_requires_transcript
        BEFORE UPDATE ON processing_records
        WHEN NEW.status = 'succeeded' AND (
            NEW.transcript_id IS NULL OR NOT EXISTS (
                SELECT 1 FROM transcripts
                WHERE id = NEW.transcript_id AND video_id = NEW.video_id
            )
        )
        BEGIN
            SELECT RAISE(ABORT, 'succeeded processing record requires its video transcript');
        END
        """
    )
    connection.execute(
        """
        CREATE TRIGGER non_success_processing_insert_has_no_transcript
        BEFORE INSERT ON processing_records
        WHEN NEW.status <> 'succeeded' AND NEW.transcript_id IS NOT NULL
        BEGIN
            SELECT RAISE(ABORT, 'non-succeeded processing record cannot link a transcript');
        END
        """
    )
    connection.execute(
        """
        CREATE TRIGGER non_success_processing_has_no_transcript
        BEFORE UPDATE ON processing_records
        WHEN NEW.status <> 'succeeded' AND NEW.transcript_id IS NOT NULL
        BEGIN
            SELECT RAISE(ABORT, 'non-succeeded processing record cannot link a transcript');
        END
        """
    )
    connection.execute(
        """
        CREATE TRIGGER prevent_linked_transcript_delete
        BEFORE DELETE ON transcripts
        WHEN EXISTS (
            SELECT 1 FROM processing_records
            WHERE transcript_id = OLD.id AND status = 'succeeded'
        )
        BEGIN
            SELECT RAISE(ABORT, 'cannot delete a transcript linked to succeeded processing');
        END
        """
    )


def _create_processing_records(
    connection: sqlite3.Connection,
    *,
    table_name: str = "processing_records",
) -> None:
    connection.execute(
        f"""
        CREATE TABLE {table_name} (
            source_type TEXT NOT NULL,
            source_url TEXT NOT NULL,
            video_id TEXT NOT NULL,
            status TEXT NOT NULL CHECK (
                status IN (
                    'pending', 'succeeded', 'failed', 'no_subtitles', 'members_only'
                )
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


def _upgrade_legacy_processing_records(connection: sqlite3.Connection) -> None:
    connection.execute(
        "ALTER TABLE processing_records RENAME TO processing_records_legacy"
    )
    _create_processing_records(connection)
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
                WHEN status = 'failed' AND error_message = ? THEN 'members_only'
                ELSE status
            END,
            attempt_count, last_attempt_at, raw_path, cleaned_path,
            language_code, is_automatic, error_message
        FROM processing_records_legacy
        """,
        (
            "该视频没有可下载的字幕。",
            "该视频为频道会员专享，TubeScribe 当前无法获取其字幕。",
        ),
    )
    connection.execute("DROP TABLE processing_records_legacy")
