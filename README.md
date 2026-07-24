# TubeWatch

TubeWatch 是面向 Windows 的 Python 视频来源监控工具，负责发现视频、保存状态、去重并显式协调后续处理。TubeScribe 作为独立安装的下层包，负责单个 YouTube 视频的字幕下载与清理。

## 当前能力

当前支持读取公开 YouTube 频道最近视频或指定播放列表、用 SQLite 识别新增，并由用户显式把待处理视频交给已安装的 TubeScribe。TubeScribe 成功后，TubeWatch 会把清理后的纯文本正文保存到 SQLite 的独立 `transcripts` 表，并在同一事务中把处理记录标为 `succeeded`；数据库写入失败时不会报告成功。首次检查时，抓取范围内的全部视频都视为新增；`check` 不会自动下载字幕。频道既可直接提供 `@wangzhian` 形式的 handle，也接受常见的 `/@handle`、`/channel/...`、`/c/...` 和 `/user/...` 完整 URL。播放列表接受标准的 `/playlist?list=...` 完整 URL。

TubeWatch 也可读取频道 `/playlists` 页面公开展示的播放列表，供 Tester 下拉选择。该清单不包含私人列表或未在频道页面公开展示的列表；选择“频道视频”时仍读取频道 `/videos`，不读取任何播放列表。

读取播放列表视频时，`limit` 表示最多返回的有效且唯一的视频数量。私密、已删除、缺少 ID 或标题的条目会被跳过，TubeWatch 会继续向后读取，直到收集满 `limit` 或播放列表结束。

播放列表读取、路由和 SQLite 去重已完成离线验证；真实 YouTube 播放列表网络验证必须由用户在 Tester 中主动运行，验证完成前不视为真实可用性结论。

`published_at`、`channel_id` 和 `channel_name` 在 yt-dlp 无法可靠提供时为 `None`。本项目不解析 YouTube HTML，也不下载视频或字幕。

## 安装

需要 Python 3.11 或以上。以下命令会把 TubeWatch 以 editable 方式安装到当前 Python 环境，不要求新建虚拟环境：

```powershell
python -m pip install -e ".[notebook]"
```

需要真实处理字幕时，可安装固定 commit 的 TubeScribe 可选依赖：

```powershell
python -m pip install -e ".[notebook,tubescribe]"
```

本地开发也可先把任意位置的 TubeScribe checkout editable 安装到同一 Python 环境；TubeWatch 的 import 和调用代码不会因此改变。

启动 Jupyter 的 Python 环境必须与安装 TubeWatch 的环境相同。可用以下命令确认正式包能够导入；打印出的安装位置仅用于诊断，不应写入项目代码：

```powershell
python -c "import tubewatch; print(tubewatch.__file__)"
```

## Notebook 验证

```powershell
jupyter lab
```

打开 `tests/notebooks/channel_tester.ipynb` 后按 cell 顺序操作。先运行到频道选择界面，输入频道并加载播放列表，明确选择频道视频或一个播放列表，并勾选真实处理确认；随后手动运行下方端到端测试 cell。Notebook 不尝试让 “Run All” 等待用户交互。

真实 workflow 每次读取并入库 3 个全新视频，只把这 3 个 ID 交给 TubeScribe。成功项会从 SQLite 重新读取 transcript，验证它与 TubeScribe TXT 一致，同时检查 SHA-256、字符数、processing 关联和 VTT 相对路径，再显示数据库正文前 20 个非空行。`no_subtitles` 和 `members_only` 都是正常业务结果，普通失败会在 cell 中明确报错。测试记录和专属字幕目录会暂时保留，便于查看 VTT；确认后运行独立清理 cell，精确删除本次视频记录、关联 transcript 和唯一的 `output/tester/<run-id>`，不触碰正式输出目录。测试 cell 报错后也应运行清理 cell。

`tests/notebooks/transcript_storage_tester.ipynb` 是完全离线的回归 Notebook，使用临时数据库和 fake TubeScribe 结果覆盖 schema、migration、repository、终态分支及事务回滚。它可以安全地从上到下执行；每项输出会说明测试目的、实际结果、期望结果和 PASS/FAIL。

Tester 通过当前 Kernel 的 `sys.executable` 调用正式 CLI，不直接导入项目源码。TubeWatch 必须先以 `.[notebook,tubescribe]` editable 安装在同一环境中。提交前应重新运行受影响的 Tester Notebook，并把不含隐私的测试结果和执行计数保留在 Notebook 中。不得提交私人 URL、Cookie、登录信息或真实字幕 sample；真实网络 Tester 必须先运行清理 cell，并确认保存的输出已脱敏。

## 命令行入口

CLI 会根据输入 URL 调用正式的频道或播放列表读取 API，供 Notebook 和人工验证使用：

```powershell
python -m tubewatch "https://www.youtube.com/@example" --limit 5
```

频道使用 handle 时可省略完整 URL：

```powershell
python -m tubewatch "@wangzhian" --limit 5
```

读取指定播放列表：

```powershell
python -m tubewatch "https://www.youtube.com/playlist?list=PL_EXAMPLE" --limit 5
```

列出频道页面公开展示的播放列表：

```powershell
python -m tubewatch playlists "@wangzhian" --json
```

结构化输出可使用：

```powershell
python -m tubewatch "https://www.youtube.com/@example" --limit 5 --json
```

也可使用安装后生成的 `tubewatch` 命令。上述无状态模式不保存状态；`check` 只发现视频，只有显式 `process` 才调用 TubeScribe 下载字幕。

有状态检查使用 `check`。默认状态文件是项目运行目录下的 `data/tubewatch.sqlite3`：

```powershell
python -m tubewatch check "https://www.youtube.com/@example" --limit 10
```

`check` 同样接受简写，例如 `python -m tubewatch check "@wangzhian" --limit 10`。

播放列表使用同一个 `check` 入口：

```powershell
python -m tubewatch check "https://www.youtube.com/playlist?list=PL_EXAMPLE" --limit 10
```

也可以明确指定数据库并取得 JSON：

```powershell
python -m tubewatch check "https://www.youtube.com/@example" `
    --state-db "D:\TubeWatchData\tubewatch.sqlite3" `
    --limit 10 `
    --json
```

`check` 只有在来源抓取完整成功后才更新数据库。频道和播放列表拥有独立来源记录；同一视频出现在两种来源中时会分别去重和排队。成功检查会立即标记视频为“已发现”；`process` 成功后标记为 `succeeded`，确认没有可下载字幕时标记为 `no_subtitles`，确认仅限频道会员访问时标记为 `members_only`。

显式处理默认只取最早的一个 pending 视频：

```powershell
python -m tubewatch process --limit 1
```

可通过 `--state-db`、`--raw-dir` 和 `--cleaned-dir` 覆盖路径，并用 `--json` 获取结构化结果。状态包括 `pending`、`succeeded`、`no_subtitles`、`members_only` 和 `failed`。`no_subtitles` 与 `members_only` 是正常终态且默认不重试；其他失败记为 `failed`，本阶段也不自动重试。

Tester 可同时提供 `--source-url` 和可重复的 `--video-id`，把处理严格限定到一个来源的精确视频集合。两个参数必须同时提供。`cleanup-test` 同样要求来源和至少一个明确的视频 ID，只删除这些发现记录及其级联处理记录：

```powershell
python -m tubewatch cleanup-test "https://www.youtube.com/@example/videos" `
    --video-id VIDEO_ID --state-db "data/tubewatch.sqlite3" --json
```

明确读取数据库中的字幕正文：

```powershell
python -m tubewatch transcript VIDEO_ID --state-db "data/tubewatch.sqlite3" --json
```

若同一视频有多语言或多来源字幕，请增加 `--language-code` 和 `--source-kind`。只有这个显式读取命令的 JSON 才包含完整 `cleaned_text`；普通 `check`、`process` 和视频列表输出只返回摘要。

## Python API

```python
from tubewatch import (
    CheckResult,
    CleanupResult,
    PlaylistItem,
    TranscriptRecord,
    VideoItem,
    check_channel_updates,
    check_playlist_updates,
    check_source_updates,
    cleanup_test_videos,
    fetch_channel_playlists,
    fetch_channel_videos,
    fetch_playlist_videos,
    fetch_source_videos,
    export_transcript_text,
    get_transcript,
    list_transcripts_for_video,
    process_pending_videos,
)

videos: list[VideoItem] = fetch_channel_videos(
    "https://www.youtube.com/@example",
    limit=5,
)

result: CheckResult = check_channel_updates(
    "https://www.youtube.com/@example",
    state_path="data/tubewatch.sqlite3",
    limit=5,
)
print(result.new_videos)

playlist = fetch_playlist_videos(
    "https://www.youtube.com/playlist?list=PL_EXAMPLE",
    limit=5,
)

playlists: list[PlaylistItem] = fetch_channel_playlists("@example")

source_result = check_source_updates(
    "https://www.youtube.com/playlist?list=PL_EXAMPLE",
    state_path="data/tubewatch.sqlite3",
    limit=5,
)

batch = process_pending_videos(
    limit=1,
    source_url=source_result.source_url,
    video_ids=[video.video_id for video in source_result.new_videos[:1]],
)
print(batch.results)

transcript: TranscriptRecord | None = get_transcript(
    "data/tubewatch.sqlite3",
    source_result.new_videos[0].video_id,
    language_code="zh",
)
if transcript is not None:
    print(transcript.character_count, transcript.cleaned_content_hash)

export_transcript_text(
    "data/tubewatch.sqlite3",
    source_result.new_videos[0].video_id,
    "exported/transcript.txt",
    language_code="zh",
)

cleanup: CleanupResult = cleanup_test_videos(
    source_result.source_url,
    [video.video_id for video in source_result.new_videos[:1]],
)
```

函数会验证 URL 和 `limit`。输入无效时抛出 `InvalidSourceError`；网络失败、来源无效或不可访问时抛出 `SourceFetchError`；SQLite 路径或读写失败时抛出 `StateStorageError`。这些异常可从 `tubewatch.exceptions` 导入。

`get_transcript` 不存在时返回 `None`。未指定足够的语言/来源选择条件且匹配多条时抛出 `AmbiguousTranscriptError`，不会随机返回。`save_transcript` 以 `(video_id, language_code, source_kind)` 幂等 upsert；`export_transcript_text` 从数据库权威正文生成 UTF-8 TXT。

## 字幕与数据库存储

- SQLite 是视频元数据、处理状态和清理后字幕正文的统一权威数据源。
- 原始 VTT 继续位于配置的 output 目录；数据库只保存相对于共同 output 根目录的路径和内容 hash。VTT 是可人工检查、可重新清理的原始产物。
- TubeScribe 目前仍会生成 cleaned TXT 以保持兼容，但 TXT 不是权威数据源。不要分别修改数据库和 TXT；需要 TXT 时应通过 `export_transcript_text` 从数据库导出。
- 普通视频查询不会加载 `cleaned_text`，只有 transcript repository 或显式 CLI 读取会加载正文。

数据库首次打开时会在单个事务中自动应用 `schema_migrations` 中尚未执行的版本；重复打开不会重复执行。旧数据库的来源、发现记录和处理记录会保留，并回填全局 `videos`。旧版 `succeeded` 没有可验证的数据库 transcript，因此会迁回 `pending` 等待显式重处理。migration 任一步失败都会整体回滚，程序不会静默重建或删除数据库。升级前仍建议先复制数据库备份。

备份 SQLite 可以保留权威正文、元数据和处理状态，但若希望保留原始可恢复材料，还必须同时备份 output 中的 raw VTT。删除数据库会丢失权威正文、元数据和状态，即使 TXT/VTT 文件仍在；删除 output/raw 会丢失原始 VTT，但不会删除数据库中的 cleaned text。删除兼容 TXT 不影响权威正文。

## TubeScribe 集成方式

TubeScribe 是外部、独立安装的 Python 包。TubeWatch 只在小型适配模块中通过 `tubescribe.workflow.process_video` 调用它，不要求两个项目位于相邻目录，不读取源码路径，也不修改 `sys.path`。

开发者可以把任意位置的本地 TubeScribe checkout editable 安装到运行 TubeWatch 的同一个 Python 环境：

```powershell
cd D:\Projects\TubeWatch
python -m pip install -e .
python -m pip install -e D:\Projects\TubeScribe
```

这些路径只是安装命令的示例，不是运行时契约。安装完成后，源码目录是否相邻不会影响标准 Python import。也可以直接从 GitHub 安装：

```powershell
python -m pip install "TubeScribe @ git+https://github.com/Htunder-Blade/TubeScribe.git@main"
```

当前可选依赖固定到已确认 commit `71f16c411c6e62b6353ed64f479099cd0ecceb62`。未来有 release 后应优先固定 release tag；不建议正式环境长期跟踪 `main`。

安装后可独立验证两个包；其实际安装位置可以不同：

```powershell
python -c "import tubewatch; print(tubewatch.__file__)"
python -c "import tubescribe; print(tubescribe.__file__)"
```

未来若需要进程级隔离，可以把 TubeScribe CLI 作为次要备用方案，但 Python API 是首选集成契约。

## 当前未支持

- TubeScribe 失败自动重试和人工重试入口
- SQLite 之外的状态后端
- transcript segments、FTS5 全文索引、embedding 和 AI 摘要
- Shorts 和直播的独立来源支持
- 视频下载（TubeScribe 只下载字幕）
- 重试、定时任务、后台服务和通知
- GUI、OpenClaw 或插件系统

## 项目结构

```text
TubeWatch/
├─ AGENTS.md
├─ README.md
├─ pyproject.toml
├─ src/tubewatch/          # API、CLI、状态、storage 与 TubeScribe 适配边界
├─ tests/notebooks/        # 离线存储回归与显式真实处理 Tester
├─ data/                   # 项目内持久状态位置（数据库不提交）
├─ output/                 # raw VTT 与兼容 TXT（产物不提交）
└─ docs/                   # 计划、架构、决策与进度
```
