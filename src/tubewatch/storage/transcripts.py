"""Repository API for authoritative cleaned transcripts."""

from __future__ import annotations

import hashlib
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from tubewatch.exceptions import AmbiguousTranscriptError, StateStorageError
from tubewatch.models import TranscriptRecord
from tubewatch.storage.database import (
    connect_database,
    initialize_database,
    resolve_database_path,
    utc_text,
)

_SOURCE_KINDS = {"manual", "auto_generated", "translated", "unknown"}


def save_transcript(
    state_path: str | Path,
    *,
    video_id: str,
    language_code: str,
    source_kind: str,
    cleaned_text: str,
    raw_file_path: str | None = None,
    source_content_hash: str | None = None,
    word_count: int | None = None,
    cleaner_name: str | None = "TubeScribe",
    cleaner_version: str | None = None,
    saved_at: datetime | None = None,
) -> TranscriptRecord:
    """Insert or update one transcript and return its stored record."""

    database_path = initialize_database(state_path)
    connection: sqlite3.Connection | None = None
    try:
        connection = connect_database(database_path)
        with connection:
            transcript_id = save_transcript_in_connection(
                connection,
                video_id=video_id,
                language_code=language_code,
                source_kind=source_kind,
                cleaned_text=cleaned_text,
                raw_file_path=raw_file_path,
                source_content_hash=source_content_hash,
                word_count=word_count,
                cleaner_name=cleaner_name,
                cleaner_version=cleaner_version,
                saved_at=saved_at,
            )
        record = _get_transcript_by_id(connection, transcript_id)
        if record is None:
            raise sqlite3.DatabaseError("保存后的 transcript 无法读取。")
        return record
    except (OSError, sqlite3.Error, ValueError) as exc:
        if isinstance(exc, StateStorageError):
            raise
        raise StateStorageError(f"无法保存 transcript：{database_path}（{exc}）") from exc
    finally:
        if connection is not None:
            connection.close()


def get_transcript(
    state_path: str | Path,
    video_id: str,
    language_code: str | None = None,
    *,
    source_kind: str | None = None,
) -> TranscriptRecord | None:
    """Return one transcript or require a more specific selector if ambiguous."""

    database_path = initialize_database(state_path)
    video_value = _required_text(video_id, "video_id")
    clauses = ["video_id = ?"]
    parameters: list[object] = [video_value]
    if language_code is not None:
        clauses.append("language_code = ?")
        parameters.append(_required_text(language_code, "language_code"))
    if source_kind is not None:
        clauses.append("source_kind = ?")
        parameters.append(_source_kind(source_kind))
    connection: sqlite3.Connection | None = None
    try:
        connection = connect_database(database_path)
        rows = connection.execute(
            f"""
            SELECT {_TRANSCRIPT_COLUMNS}
            FROM transcripts
            WHERE {' AND '.join(clauses)}
            ORDER BY language_code, source_kind, id
            LIMIT 2
            """,
            tuple(parameters),
        ).fetchall()
        if not rows:
            return None
        if len(rows) > 1:
            raise AmbiguousTranscriptError(
                "匹配到多条 transcript，请明确指定 language_code 和 source_kind。"
            )
        return _record_from_row(rows[0])
    except AmbiguousTranscriptError:
        raise
    except (OSError, sqlite3.Error, ValueError) as exc:
        raise StateStorageError(f"无法读取 transcript：{database_path}（{exc}）") from exc
    finally:
        if connection is not None:
            connection.close()


def list_transcripts_for_video(
    state_path: str | Path,
    video_id: str,
) -> list[TranscriptRecord]:
    """Return all explicitly requested transcripts for one video."""

    database_path = initialize_database(state_path)
    video_value = _required_text(video_id, "video_id")
    connection: sqlite3.Connection | None = None
    try:
        connection = connect_database(database_path)
        rows = connection.execute(
            f"""
            SELECT {_TRANSCRIPT_COLUMNS}
            FROM transcripts
            WHERE video_id = ?
            ORDER BY language_code, source_kind, id
            """,
            (video_value,),
        ).fetchall()
        return [_record_from_row(row) for row in rows]
    except (OSError, sqlite3.Error, ValueError) as exc:
        raise StateStorageError(f"无法列出 transcript：{database_path}（{exc}）") from exc
    finally:
        if connection is not None:
            connection.close()


def delete_transcript(state_path: str | Path, transcript_id: int) -> bool:
    """Delete one transcript by ID and report whether it existed."""

    if isinstance(transcript_id, bool) or not isinstance(transcript_id, int):
        raise ValueError("transcript_id 必须是整数。")
    database_path = initialize_database(state_path)
    connection: sqlite3.Connection | None = None
    try:
        connection = connect_database(database_path)
        with connection:
            cursor = connection.execute(
                "DELETE FROM transcripts WHERE id = ?", (transcript_id,)
            )
        return cursor.rowcount == 1
    except (OSError, sqlite3.Error) as exc:
        raise StateStorageError(f"无法删除 transcript：{database_path}（{exc}）") from exc
    finally:
        if connection is not None:
            connection.close()


def export_transcript_text(
    state_path: str | Path,
    video_id: str,
    destination: str | Path,
    language_code: str | None = None,
    *,
    source_kind: str | None = None,
) -> Path:
    """Export one authoritative transcript as a UTF-8 TXT file."""

    transcript = get_transcript(
        state_path,
        video_id,
        language_code,
        source_kind=source_kind,
    )
    if transcript is None:
        raise StateStorageError(f"video_id={video_id!r} 没有匹配的 transcript。")
    try:
        output_path = Path(destination).expanduser().resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(transcript.cleaned_text, encoding="utf-8")
        return output_path
    except (OSError, TypeError, ValueError) as exc:
        raise StateStorageError(f"无法导出 transcript：{destination}（{exc}）") from exc


def save_transcript_in_connection(
    connection: sqlite3.Connection,
    *,
    video_id: str,
    language_code: str,
    source_kind: str,
    cleaned_text: str,
    raw_file_path: str | None,
    source_content_hash: str | None,
    word_count: int | None,
    cleaner_name: str | None,
    cleaner_version: str | None,
    saved_at: datetime | None,
) -> int:
    """Upsert a transcript within a caller-owned transaction."""

    video_value = _required_text(video_id, "video_id")
    language_value = _required_text(language_code, "language_code")
    source_value = _source_kind(source_kind)
    if not isinstance(cleaned_text, str) or not cleaned_text.strip():
        raise ValueError("cleaned_text 必须是非空字符串。")
    invalid_word_count = (
        isinstance(word_count, bool)
        or not isinstance(word_count, int)
        or word_count < 0
    )
    if word_count is not None and invalid_word_count:
        raise ValueError("word_count 必须是非负整数或 None。")
    timestamp = utc_text(saved_at or datetime.now(tz=UTC))
    cleaned_hash = hashlib.sha256(cleaned_text.encode("utf-8")).hexdigest()
    character_count = len(cleaned_text)
    raw_path_value = _relative_file_path(raw_file_path)
    connection.execute(
        """
        INSERT INTO transcripts (
            video_id, language_code, source_kind, format, cleaned_text,
            cleaner_name, cleaner_version, source_content_hash,
            cleaned_content_hash, character_count, word_count, raw_file_path,
            created_at, updated_at
        ) VALUES (?, ?, ?, 'plain_text', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT (video_id, language_code, source_kind) DO UPDATE SET
            cleaned_text = excluded.cleaned_text,
            cleaner_name = excluded.cleaner_name,
            cleaner_version = excluded.cleaner_version,
            source_content_hash = excluded.source_content_hash,
            cleaned_content_hash = excluded.cleaned_content_hash,
            character_count = excluded.character_count,
            word_count = excluded.word_count,
            raw_file_path = excluded.raw_file_path,
            updated_at = excluded.updated_at
        WHERE transcripts.cleaned_content_hash <> excluded.cleaned_content_hash
           OR transcripts.source_content_hash IS NOT excluded.source_content_hash
           OR transcripts.raw_file_path IS NOT excluded.raw_file_path
           OR transcripts.cleaner_name IS NOT excluded.cleaner_name
           OR transcripts.cleaner_version IS NOT excluded.cleaner_version
           OR transcripts.word_count IS NOT excluded.word_count
        """,
        (
            video_value,
            language_value,
            source_value,
            cleaned_text,
            cleaner_name,
            cleaner_version,
            source_content_hash,
            cleaned_hash,
            character_count,
            word_count,
            raw_path_value,
            timestamp,
            timestamp,
        ),
    )
    row = connection.execute(
        """
        SELECT id FROM transcripts
        WHERE video_id = ? AND language_code = ? AND source_kind = ?
        """,
        (video_value, language_value, source_value),
    ).fetchone()
    if row is None:
        raise sqlite3.DatabaseError("transcript upsert 未返回记录。")
    return int(row[0])


_TRANSCRIPT_COLUMNS = """
    id, video_id, language_code, source_kind, format, cleaned_text,
    cleaner_name, cleaner_version, source_content_hash, cleaned_content_hash,
    character_count, word_count, raw_file_path, created_at, updated_at
"""


def _get_transcript_by_id(
    connection: sqlite3.Connection,
    transcript_id: int,
) -> TranscriptRecord | None:
    row = connection.execute(
        f"SELECT {_TRANSCRIPT_COLUMNS} FROM transcripts WHERE id = ?",
        (transcript_id,),
    ).fetchone()
    return _record_from_row(row) if row is not None else None


def _record_from_row(row: tuple[object, ...]) -> TranscriptRecord:
    return TranscriptRecord(
        id=int(row[0]),
        video_id=str(row[1]),
        language_code=str(row[2]),
        source_kind=str(row[3]),
        format=str(row[4]),
        cleaned_text=str(row[5]),
        cleaner_name=str(row[6]) if row[6] is not None else None,
        cleaner_version=str(row[7]) if row[7] is not None else None,
        source_content_hash=str(row[8]) if row[8] is not None else None,
        cleaned_content_hash=str(row[9]),
        character_count=int(row[10]),
        word_count=int(row[11]) if row[11] is not None else None,
        raw_file_path=str(row[12]) if row[12] is not None else None,
        created_at=datetime.fromisoformat(str(row[13])),
        updated_at=datetime.fromisoformat(str(row[14])),
    )


def _required_text(value: str, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} 不能为空。")
    return value.strip()


def _source_kind(value: str) -> str:
    normalized = _required_text(value, "source_kind")
    if normalized not in _SOURCE_KINDS:
        raise ValueError(f"不支持的 source_kind：{normalized}")
    return normalized


def _relative_file_path(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = _required_text(value, "raw_file_path")
    path = Path(normalized)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError("raw_file_path 必须是 output 根目录内的相对路径。")
    return path.as_posix()
