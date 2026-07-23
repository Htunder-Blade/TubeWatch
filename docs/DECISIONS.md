# 关键决定

1. 当前先实现频道，播放列表留到 Phase 3。
2. 使用 yt-dlp 获取公开频道信息，不自行解析 YouTube HTML。
3. 当前使用 Notebook 做真实 workflow 验证，不另建 pytest 体系，也不自动运行网络测试。
4. Phase 0 不集成 TubeScribe、不下载视频或字幕；该决定已由 Phase 2 的显式 `process` 模式扩展。
5. 当前不建立数据库或任何历史状态文件。
6. 对外返回项目自己的 `VideoItem`，不暴露 yt-dlp 原始字典。
7. 无法可靠取得的元数据使用 `None`，不推测或伪造。
8. 当前只读取频道的“视频”标签页，支持范围在 README 中明确说明。
9. TubeScribe 将作为外部、独立安装的 Python 包集成；不使用 sibling-directory integration，不要求两个源码项目相邻。
10. TubeWatch 不修改 `sys.path`，不从 TubeScribe 的源码路径或相对路径导入，也不自动扫描磁盘、下载源码或执行 pip。
11. 本地 editable install 只是开发安装方式，不构成运行时目录耦合；无论 TubeScribe 来自本地 checkout、GitHub、固定 commit 或 release，TubeWatch 都使用相同的标准 import。
12. 正式可复现环境优先固定 TubeScribe release tag；暂无 release 时固定 commit SHA，不长期跟踪 `main`，也不虚构尚不存在的版本引用。
13. 优先通过 TubeScribe 公开 Python API 集成，外部 TubeScribe CLI 仅为次要备用方案；缺少依赖时提供明确错误，不进行隐式回退。
14. Phase 0 只确定上述集成契约，不声明 TubeScribe 依赖，不创建适配器，也不调用 TubeScribe 或下载字幕。
15. Channel Tester 与 TubeScribe Tester 采用相同的子进程模式：使用当前 Kernel 的 `sys.executable` 调用 `python -m tubewatch`，而不是在 Notebook 中直接 import 或修改路径。
16. 为支持该验证入口，Phase 0 提供只包装现有频道 API 的最小 CLI；它不引入状态、下载、TubeScribe 或其他新业务能力。
17. 开发中的 TubeWatch editable 安装到当前 base Python 环境；安装是标准包发现机制，不代表正式发布，也不造成源码目录硬编码。
18. Phase 1 使用 Python 标准库 SQLite 保存状态，不增加数据库依赖；默认路径为 `data/tubewatch.sqlite3`，并允许调用者覆盖。
19. 首次成功检查把抓取范围内全部视频视为新增；以后按规范化来源 URL 与 video ID 去重。
20. “已发现”在成功检查的单个数据库事务中立即记录，与未来 TubeScribe 的“已处理”状态分离。
21. 频道抓取必须先完整成功，随后才允许打开和更新状态数据库；抓取失败不得改变状态。
22. 保留原有无状态 CLI，用 `tubewatch check` 显式进入有状态模式；Notebook 使用项目内 `data/tubewatch.sqlite3` 录入并保留真实发现记录，同时用连续两次检查验证去重。
23. `data/` 目录属于项目结构，数据库文件属于用户运行状态并由 Git 忽略；重复运行 Tester 不重置历史记录。
24. Phase 2 使用显式 `process`，`check` 不自动下载字幕；默认每批只处理一个 pending 视频。
25. TubeScribe 是固定到 commit `71f16c411c6e62b6353ed64f479099cd0ecceb62` 的可选依赖，本地 editable install 只改变安装来源。
26. TubeScribe 调用只存在于小型适配模块，并转换为 TubeWatch 结果与异常。
27. 处理状态分为 `pending/succeeded/no_subtitles/members_only/failed`；确认无人工或自动字幕时记录 `no_subtitles`，确认仅限频道会员访问时记录 `members_only`，两者都是默认不重试的正常终态，其他失败仍记录为 `failed`。
28. 默认字幕产物位于 `output/raw` 和 `output/cleaned`，产物不进入版本控制。
29. Tester 自动处理下一条 pending；`succeeded`、`no_subtitles` 与 `members_only` 都算 workflow 通过，只有普通 `failed` 才抛出测试错误。
30. 同一时间批量发现的视频按数据库录入顺序处理，不以 video ID 重新排序。
31. 频道输入除完整 YouTube URL 外也接受 `@handle` 简写；两种形式统一规范化为相同的 `https://www.youtube.com/@handle/videos` 来源 URL，以保持去重一致。
32. Phase 3 支持标准 `https://www.youtube.com/playlist?list=...` URL；播放列表在独立适配模块中输出相同的 `VideoItem`，不接受带 `list` 参数的单视频 watch URL 作为来源。
33. CLI 和通用 Python API 根据标准播放列表 URL 路由，显式频道与播放列表 API 继续保留；SQLite 使用 `source_type=playlist` 和只保留 `list` 参数的规范化 URL 独立去重，无需 schema 迁移。
34. Phase 3 初始 Tester 配置不使用混合含义的单一 `source_url`；频道 handle 与选填播放列表 URL 分别调用 CLI 并独立验证去重。该配置界面随后由决定 35 的单选交互取代。
35. Tester 改为先通过正式 `playlists` CLI 读取频道页面公开展示的播放列表，再从频道视频或一个播放列表中选择单一来源；Notebook 不实现 yt-dlp 提取逻辑。
36. 首期来源选择只限定 `check`，不改变 `process` 从数据库全局最早 pending 记录取任务的行为；真实字幕处理继续默认关闭。
37. 端到端 Tester 用 `source_url + video_ids` 同时限定 `process`，避免消费共享测试库中的其他 pending；不带过滤参数的正式处理行为保持不变。
38. Tester 每次要求读取并尝试处理 3 个全新视频；成功项展示清理文本前 20 个非空行，`no_subtitles` 与 `members_only` 仍算正常业务结果，普通失败使测试失败。
39. Tester 将本次规范化来源、精确 ID 和唯一 `output/tester/<run-id>` 保存在运行上下文中；用户查看 sample 后通过独立清理 cell 删除数据库记录和测试目录，不删除数据库文件、不无条件清表，也不触碰正式字幕目录。
40. Tester 采用手动逐 cell 流程，不试图让 “Run All” 等待 widget 交互：来源选择后的测试 cell 执行真实 workflow，最后的清理 cell 明确回收本次数据；未清理时拒绝开始下一次测试。
41. 播放列表的 `limit` 约束最终有效且唯一的视频集合，而不是原始位置数；适配器分批向后读取并跳过私密、删除、字段不完整和重复条目，直到补足数量或列表结束。
42. TubeWatch 显式捕获 TubeScribe 的 `WorkflowMembersOnlyError` 并记录 `members_only` 正常终态；该结果不生成字幕产物、不自动重试，也不使 CLI 或 Tester 失败。
43. 增加全局 `videos` 和独立 `transcripts`；字幕不绑定来源发现记录，也不把大正文放进视频元数据行。
44. SQLite cleaned text 是权威数据源；raw VTT 留在文件系统并只在数据库保存 output 相对路径，TXT 降为兼容或导出产物。
45. `processing_records.transcript_id` 明确链接成功产物；transcript upsert 与 `succeeded` 更新必须位于同一事务，schema trigger 同时保护该不变量。
46. 使用内建的有序 `schema_migrations`；新旧数据库都事务性升级，失败整体回滚，旧版无 transcript 的 `succeeded` 迁回 `pending`。
47. transcript 读取必须显式；无选择条件只在唯一匹配时返回，多匹配抛出 `AmbiguousTranscriptError`，普通视频列表不加载正文。
48. 本阶段提供 Python TXT 导出 API 和显式 `transcript` CLI 读取；不实现 segments、FTS5、embedding 或 AI 摘要。
