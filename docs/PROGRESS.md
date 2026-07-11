# 当前进度

## 已完成（Phase 0 至 Phase 2）

- 建立 Python 3.11+ `src` 布局和项目元数据。
- 定义稳定的 `VideoItem` 数据模型和项目级异常。
- 实现公开 YouTube 频道最近视频读取 API，限制结果数量且不下载媒体。
- 建立无私人数据、无输出的 Notebook workflow 验证入口。
- 记录项目定位、架构边界、关键决定和后续计划。
- 明确未来通过正常安装的 TubeScribe Python 包集成，不依赖相邻目录、源码路径或 `sys.path` 修改。
- 记录正式环境固定 release tag 或 commit SHA、本地 editable install 仅用于开发的可复现依赖策略。
- 增加只包装频道读取 API 的最小 `python -m tubewatch`/`tubewatch` CLI。
- 将 Channel Tester 改为与 TubeScribe Tester 相同的 `sys.executable` 子进程调用模式，不在 Notebook 中直接导入项目源码。
- 已将 TubeWatch editable 安装到当前 Anaconda base Python 环境，并离线验证帮助、输入错误退出码和结构化 JSON 输出。
- 定义 `CheckResult` 和 `check_channel_updates` 正式 API。
- 使用 SQLite 按来源和 video ID 保存发现状态，首次全部新增、重复检查去重。
- 增加 `tubewatch check`、可选状态路径及普通/JSON 输出，同时保留无状态 CLI。
- 将抓取与状态事务分隔，保证抓取失败不创建或更新数据库。
- Channel Tester 使用项目内 `data/tubewatch.sqlite3` 录入并保留真实发现记录，同时连续检查两次验证去重。
- Phase 1 已由项目数据库中的 1 个频道和 10 条发现记录真实验证。
- 增加固定 commit 的 TubeScribe 可选依赖、最小 Python API 适配器和明确缺失依赖错误。
- 增加 `processing_records`、`process_pending_videos` 与 `tubewatch process`，默认显式处理一条 pending 视频。
- 记录成功输出或失败原因；失败不自动重试，字幕产物写入项目 `output/`。
- 将无字幕从普通失败中分离为 `no_subtitles` 正常终态；Tester 可验证成功或无字幕两条真实分支。
- Phase 2 已在 Notebook 中由用户显式启用 TubeScribe 完成真实验证：已确认字幕成功产出以及 `no_subtitles` 正常终态。

## 尚未完成

- 播放列表来源。
- 普通处理失败的重试、定时运行和通知；`no_subtitles` 默认不重试。
- 后台服务、GUI 和 OpenClaw 集成。
