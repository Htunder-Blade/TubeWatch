"""Command-line entry point for the current channel-reading workflow."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence

from tubewatch.checks import check_channel_updates
from tubewatch.exceptions import (
    InvalidProcessingOptionError,
    InvalidSourceError,
    SourceFetchError,
    StateStorageError,
    TubeScribeUnavailableError,
)
from tubewatch.models import CheckResult, ProcessingBatchResult, ProcessingItemResult, VideoItem
from tubewatch.processing import process_pending_videos
from tubewatch.youtube.channel import fetch_channel_videos


def main(argv: Sequence[str] | None = None) -> int:
    """Run the TubeWatch channel reader and return a process exit code."""

    arguments_list = list(argv) if argv is not None else sys.argv[1:]
    if arguments_list and arguments_list[0] == "check":
        return _run_check(arguments_list[1:])
    if arguments_list and arguments_list[0] == "process":
        return _run_process(arguments_list[1:])
    return _run_fetch(arguments_list)


def _run_fetch(argv: Sequence[str]) -> int:
    parser = _build_fetch_parser()
    arguments = parser.parse_args(argv)
    try:
        videos = fetch_channel_videos(arguments.channel_url, limit=arguments.limit)
    except InvalidSourceError as exc:
        parser.error(str(exc))
    except SourceFetchError as exc:
        print(f"TubeWatch：{exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("TubeWatch：用户已中断。", file=sys.stderr)
        return 130

    if arguments.json:
        print(
            json.dumps(
                [_video_to_dict(video) for video in videos],
                ensure_ascii=False,
            )
        )
    else:
        print(f"返回视频数量：{len(videos)}")
        for index, video in enumerate(videos, start=1):
            print(f"\n[{index}] {video.title}")
            print(f"video ID：{video.video_id}")
            print(f"URL：{video.url}")
            print(f"发布时间：{video.published_at}")
            print(f"频道名称：{video.channel_name}")
    return 0


def _run_check(argv: Sequence[str]) -> int:
    parser = _build_check_parser()
    arguments = parser.parse_args(argv)
    try:
        result = check_channel_updates(
            arguments.channel_url,
            state_path=arguments.state_db,
            limit=arguments.limit,
        )
    except InvalidSourceError as exc:
        parser.error(str(exc))
    except (SourceFetchError, StateStorageError) as exc:
        print(f"TubeWatch：{exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("TubeWatch：用户已中断。", file=sys.stderr)
        return 130

    if arguments.json:
        print(json.dumps(_check_result_to_dict(result), ensure_ascii=False))
    else:
        print(f"本次读取视频数量：{result.fetched_count}")
        print(f"新增视频数量：{len(result.new_videos)}")
        for index, video in enumerate(result.new_videos, start=1):
            print(f"\n[{index}] {video.title}")
            print(f"video ID：{video.video_id}")
            print(f"URL：{video.url}")
            print(f"发布时间：{video.published_at}")
            print(f"频道名称：{video.channel_name}")
    return 0


def _run_process(argv: Sequence[str]) -> int:
    parser = _build_process_parser()
    arguments = parser.parse_args(argv)
    try:
        result = process_pending_videos(
            state_path=arguments.state_db,
            raw_directory=arguments.raw_dir,
            cleaned_directory=arguments.cleaned_dir,
            limit=arguments.limit,
        )
    except InvalidProcessingOptionError as exc:
        parser.error(str(exc))
    except (StateStorageError, TubeScribeUnavailableError) as exc:
        print(f"TubeWatch：{exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("TubeWatch：用户已中断。", file=sys.stderr)
        return 130

    if arguments.json:
        print(json.dumps(_processing_batch_to_dict(result), ensure_ascii=False))
    else:
        print(f"本次尝试处理数量：{result.attempted_count}")
        print(f"剩余待处理数量：{result.pending_remaining}")
        for item in result.results:
            print(f"\n[{item.status}] {item.title}")
            print(f"video ID：{item.video_id}")
            if item.status == "succeeded":
                print(f"原始字幕：{item.raw_path}")
                print(f"清理文本：{item.cleaned_path}")
                print(f"字幕语言：{item.language_code}")
            elif item.status == "no_subtitles":
                print(f"无字幕：{item.error_message}")
            else:
                print(f"错误：{item.error_message}")
    return 1 if any(item.status == "failed" for item in result.results) else 0


def _build_fetch_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="tubewatch",
        description="读取公开 YouTube 频道最近的视频。",
        epilog=(
            "有状态新增检测：tubewatch check CHANNEL_URL；"
            "显式字幕处理：tubewatch process"
        ),
    )
    parser.add_argument("channel_url", help="YouTube 频道主页 URL 或 @handle")
    parser.add_argument("--limit", type=int, default=10, help="最多返回的视频数量")
    parser.add_argument("--json", action="store_true", help="以 JSON 输出稳定字段")
    return parser


def _build_check_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="tubewatch check",
        description="读取公开 YouTube 频道并记录已发现的视频。",
    )
    parser.add_argument("channel_url", help="YouTube 频道主页 URL 或 @handle")
    parser.add_argument("--limit", type=int, default=10, help="最多返回的视频数量")
    parser.add_argument(
        "--state-db",
        default="data/tubewatch.sqlite3",
        help="SQLite 状态数据库路径",
    )
    parser.add_argument("--json", action="store_true", help="以 JSON 输出稳定字段")
    return parser


def _build_process_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="tubewatch process",
        description="通过 TubeScribe 显式处理待处理视频。",
    )
    parser.add_argument("--limit", type=int, default=1, help="本次最多处理的视频数量")
    parser.add_argument(
        "--state-db",
        default="data/tubewatch.sqlite3",
        help="SQLite 状态数据库路径",
    )
    parser.add_argument("--raw-dir", default="output/raw", help="原始字幕输出目录")
    parser.add_argument(
        "--cleaned-dir",
        default="output/cleaned",
        help="清理文本输出目录",
    )
    parser.add_argument("--json", action="store_true", help="以 JSON 输出稳定字段")
    return parser


def _video_to_dict(video: VideoItem) -> dict[str, str | None]:
    return {
        "video_id": video.video_id,
        "title": video.title,
        "url": video.url,
        "published_at": video.published_at.isoformat()
        if video.published_at is not None
        else None,
        "channel_id": video.channel_id,
        "channel_name": video.channel_name,
    }


def _check_result_to_dict(result: CheckResult) -> dict[str, object]:
    return {
        "source_url": result.source_url,
        "checked_at": result.checked_at.isoformat(),
        "fetched_count": result.fetched_count,
        "new_count": len(result.new_videos),
        "new_videos": [_video_to_dict(video) for video in result.new_videos],
    }


def _processing_item_to_dict(item: ProcessingItemResult) -> dict[str, object]:
    return {
        "source_url": item.source_url,
        "video_id": item.video_id,
        "title": item.title,
        "status": item.status,
        "attempted_at": item.attempted_at.isoformat(),
        "raw_path": str(item.raw_path) if item.raw_path is not None else None,
        "cleaned_path": str(item.cleaned_path) if item.cleaned_path is not None else None,
        "language_code": item.language_code,
        "is_automatic": item.is_automatic,
        "error_message": item.error_message,
    }


def _processing_batch_to_dict(result: ProcessingBatchResult) -> dict[str, object]:
    return {
        "attempted_count": result.attempted_count,
        "pending_remaining": result.pending_remaining,
        "succeeded_count": sum(item.status == "succeeded" for item in result.results),
        "no_subtitles_count": sum(
            item.status == "no_subtitles" for item in result.results
        ),
        "failed_count": sum(item.status == "failed" for item in result.results),
        "results": [_processing_item_to_dict(item) for item in result.results],
    }
