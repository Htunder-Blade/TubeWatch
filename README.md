# TubeWatch

TubeWatch 是面向 Windows 的 Python 视频来源监控工具，负责发现视频、保存状态、去重并显式协调后续处理。TubeScribe 作为独立安装的下层包，负责单个 YouTube 视频的字幕下载与清理。

## 当前能力

当前支持读取公开 YouTube 频道最近视频、用 SQLite 识别新增，并由用户显式把待处理视频交给已安装的 TubeScribe。首次检查时，抓取范围内的全部视频都视为新增；`check` 不会自动下载字幕。当前接受常见的 `/@handle`、`/channel/...`、`/c/...` 和 `/user/...` 频道 URL。

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

打开 `tests/notebooks/channel_tester.ipynb`，在配置单元格中临时填写频道 URL，然后逐格执行。Tester 通过当前 Kernel 的 `sys.executable` 启动 `python -m tubewatch` 子进程，不直接导入项目源码；它把发现记录持久写入项目内的 `data/tubewatch.sqlite3`，并连续检查两次以验证去重。数据库会跨 Notebook 运行保留，因此以后运行时第一次检查也可能是零条新增。TubeWatch 必须先 editable 安装在这个 Python 环境中。不要保存包含私人 URL、Cookie 或运行输出的 Notebook。

`data/tubewatch.sqlite3` 是本地运行数据并已被 Git 忽略。配置中的 `run_tubescribe = False` 默认禁止字幕处理；只有用户显式改为 `True` 才会处理下一条 pending 视频。成功时验证 VTT/TXT；确认无字幕时验证 `no_subtitles` 终态，这两种结果都表示 workflow 正常。输出写入 `output/raw` 与 `output/cleaned`。

## 命令行入口

当前最小 CLI 只包装正式频道读取 API，供 Notebook 和人工验证使用：

```powershell
python -m tubewatch "https://www.youtube.com/@example" --limit 5
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

也可以明确指定数据库并取得 JSON：

```powershell
python -m tubewatch check "https://www.youtube.com/@example" `
    --state-db "D:\TubeWatchData\tubewatch.sqlite3" `
    --limit 10 `
    --json
```

`check` 只有在频道抓取完整成功后才更新数据库。成功检查会立即标记视频为“已发现”；`process` 成功后标记为 `succeeded`，确认没有可下载字幕时标记为 `no_subtitles`。

显式处理默认只取最早的一个 pending 视频：

```powershell
python -m tubewatch process --limit 1
```

可通过 `--state-db`、`--raw-dir` 和 `--cleaned-dir` 覆盖路径，并用 `--json` 获取结构化结果。状态包括 `pending`、`succeeded`、`no_subtitles` 和 `failed`。`no_subtitles` 是正常终态且默认不重试；其他失败记为 `failed`，本阶段也不自动重试。

## Python API

```python
from tubewatch import (
    CheckResult,
    VideoItem,
    check_channel_updates,
    fetch_channel_videos,
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

batch = process_pending_videos(limit=1)
print(batch.results)
```

函数会验证 URL 和 `limit`。输入无效时抛出 `InvalidSourceError`；网络失败、频道无效或不可访问时抛出 `SourceFetchError`；SQLite 路径或读写失败时抛出 `StateStorageError`。这些异常可从 `tubewatch.exceptions` 导入。

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

当前可选依赖固定到已确认 commit `8681acc49d8a897aeff7bea9801869e740109b8d`。未来有 release 后应优先固定 release tag；不建议正式环境长期跟踪 `main`。

安装后可独立验证两个包；其实际安装位置可以不同：

```powershell
python -c "import tubewatch; print(tubewatch.__file__)"
python -c "import tubescribe; print(tubescribe.__file__)"
```

未来若需要进程级隔离，可以把 TubeScribe CLI 作为次要备用方案，但 Python API 是首选集成契约。

## 当前未支持

- TubeScribe 失败自动重试和人工重试入口
- SQLite 之外的状态后端或数据库迁移工具
- 播放列表和 Shorts/直播的独立来源支持
- 视频下载（TubeScribe 只下载字幕）
- 重试、定时任务、后台服务和通知
- GUI、OpenClaw 或插件系统

## 项目结构

```text
TubeWatch/
├─ AGENTS.md
├─ README.md
├─ pyproject.toml
├─ src/tubewatch/          # API、CLI、状态与 TubeScribe 适配边界
├─ tests/notebooks/        # 持久验证发现，并可显式验证一条字幕处理
├─ data/                   # 项目内持久状态位置（数据库不提交）
├─ output/                 # TubeScribe VTT/TXT（产物不提交）
└─ docs/                   # 计划、架构、决策与进度
```
