# 当前进度

## 已完成（Phase 0 至 Phase 2，以及 Phase 3 实现）

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
- 增加公开 YouTube 播放列表读取 API，并将标准 `/playlist?list=...` URL 路由到独立来源适配器。
- 增加播放列表有状态检查；使用 `source_type=playlist` 与规范化 URL 独立去重，不改变现有数据库 schema。
- 扩展 CLI、公共 Python API 和 Tester；Tester 通过正式 CLI 加载频道公开播放列表，并从频道视频或一个播放列表中选择单一 `check` 来源。
- Phase 3 已通过离线 URL、适配转换、CLI 路由和 SQLite 去重回归；真实播放列表网络 workflow 尚待用户在 Tester 中主动验证。
- 增加频道公开播放列表发现 API 和 `playlists` CLI。
- 播放列表发现与选择已完成离线回归；真实频道 `/playlists` 页面和交互 workflow 尚待用户在 Tester 中主动验证。
- 播放列表视频读取会跳过私密、删除、字段不完整及重复条目并继续向后补足 `limit`；已通过离线批次回归和同一测试来源的只读元数据验证。
- 增加来源与 video ID 联合过滤的 `process`，以及只删除明确视频集合的 `cleanup-test`。
- Tester 已改为手动逐 cell 流程：选择频道来源并确认后，下一 cell 对 3 个视频执行处理并保留成功字幕 sample；最后的独立清理 cell 精确删除本次数据库记录和专属输出目录，未清理时不能开始下一次测试。
- Phase 3 Tester 已由用户完成一次真实播放列表运行：频道播放列表加载与选择成功，两个公开视频成功生成字幕 sample，第三个会员专享视频按普通失败报告，随后精确清理数据库和专属输出目录。

## 尚未完成

- Phase 3 的真实 YouTube 播放列表网络验证。
- 频道播放列表下拉选择及 3 视频端到端 Tester 的真实网络验证。
- 播放列表 flat metadata 中有标题但属于 `subscriber_only`、`premium_only` 或 `needs_auth` 的条目仍可能进入处理；下一步应在发现阶段过滤访问受限条目并继续向后补足有效公开视频。
- 普通处理失败的重试、定时运行和通知；`no_subtitles` 默认不重试。
- 后台服务、GUI 和 OpenClaw 集成。
