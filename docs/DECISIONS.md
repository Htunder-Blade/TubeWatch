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
25. TubeScribe 是固定到 commit `8681acc49d8a897aeff7bea9801869e740109b8d` 的可选依赖，本地 editable install 只改变安装来源。
26. TubeScribe 调用只存在于小型适配模块，并转换为 TubeWatch 结果与异常。
27. 处理状态分为 `pending/succeeded/no_subtitles/failed`；确认无人工或自动字幕时记录 `no_subtitles`，它是默认不重试的正常终态，其他失败仍记录为 `failed`。
28. 默认字幕产物位于 `output/raw` 和 `output/cleaned`，产物不进入版本控制。
29. Tester 自动处理下一条 pending；`succeeded` 与正确记录的 `no_subtitles` 都算 workflow 通过，只有普通 `failed` 才抛出测试错误。
30. 同一时间批量发现的视频按数据库录入顺序处理，不以 video ID 重新排序。
