# 架构

TubeWatch 是有状态的上层监控工具：读取“视频来源”，通过 SQLite 识别此前未发现的视频，并显式协调处理任务。TubeScribe 是外部、独立安装的下层 Python 包，负责单视频字幕处理。

“视频来源”是项目的通用概念。频道和播放列表是当前实现的两种来源，各自在独立模块中提供相同的稳定 `VideoItem` 输出。通用入口只负责根据标准播放列表 URL 路由，不建立抽象基类、大量接口或插件系统。

频道播放列表发现是来源选择辅助能力，不是第三种状态来源。它读取频道 `/playlists` 页面并返回稳定 `PlaylistItem`，由调用者选出一个标准播放列表 URL；真正检查时仍使用既有的 `channel` 或 `playlist` 来源类型。

```text
Notebook -> python -m tubewatch check -> CLI -> youtube.channel  --\
                                            -> youtube.playlist --+-> list[VideoItem]
                                                                   |
                                                                   v
                                                         SQLite discovered_videos
                                                                   |
                                                                   v
                                                            CheckResult.new_videos
                                                                   |
                                                         explicit process command
                                                                   |
                                                                   v
                                                 TubeScribe API -> output/raw + output/cleaned
```

第三方 yt-dlp 数据只存在于来源适配模块内部。项目对外暴露自己的不可变数据模型，并把预期失败转换成项目级异常。

当前 CLI 是正式 Python API 的薄适配层，只负责解析来源 URL、`limit` 和输出格式，并把项目级异常映射为稳定退出码。标准 `/playlist?list=...` URL 路由到播放列表适配器，其他输入保持现有频道与 `@handle` 语义；`playlists` 子命令只列出频道公开播放列表，不写状态。Tester 先调用该命令填充单选下拉菜单，再把频道或一个播放列表交给同一 `check` workflow。Notebook 与 TubeScribe Tester 使用相同的进程边界：由当前 Kernel 的 `sys.executable` 启动模块入口，在子进程中调用正式代码。Notebook 不直接导入 `src`、不修改 `sys.path`，也不复制来源读取逻辑。editable install 让开发中的源码通过标准包机制立即可用，不表示项目已经发布或完成。

播放列表视频适配器按位置分批读取 flat metadata，将私密、删除、字段不完整和重复的视频跳过后继续下一批；因此 `limit` 限制最终有效且唯一的视频数量，而不是原始播放列表的前 N 个位置。只有收集满数量或确认播放列表结束时才停止。

## SQLite 状态边界

频道和播放列表检查都先完整读取来源，只有读取成功后才打开并事务性更新 SQLite。数据库以 `source_type + source_url + video_id` 唯一标识一条发现记录，因此同一视频可分别属于不同来源。来源 URL 使用对应适配模块的规范化结果；`source_type` 当前为 `channel` 或 `playlist`。

首次检查会把抓取范围内的全部视频返回为新增；检查成功后立即记录“已发现”。`first_seen_at` 保持不变，后续检查会更新元数据和 `last_seen_at`。发现状态与 TubeScribe 处理状态严格分离；处理结果单独写入 `processing_records`。

`processing_records` 为每条发现记录保存 `pending/succeeded/no_subtitles/members_only/failed`、尝试次数、输出路径、字幕语言与错误。`no_subtitles` 表示 TubeScribe 已确认没有人工或自动字幕，`members_only` 表示视频仅限频道会员访问，两者都是正常终态；`failed` 保留给网络、文件和其他处理错误。历史发现记录幂等补为 `pending`，旧的明确无字幕或会员专享失败会迁移为对应终态。`process` 只选择 pending，默认一次一条；终态和失败记录不再自动选择。

默认 `process` 继续按全局发现顺序取 pending；Tester 同时传入规范化来源和精确 video ID 集合时，状态查询和剩余计数都限定到该集合。独立清理 cell 通过 `cleanup-test` 在单个事务中删除这些精确发现记录，处理记录通过外键级联删除，来源没有剩余视频时才删除来源行。Tester 字幕写入唯一的 `output/tester/<run-id>`，数据库和文件清理互相独立执行。

Notebook 采用显式的逐 cell 交互，不为 “Run All” 实现等待或暂停。用户在频道选择 cell 的 widget 中加载并选择来源、确认真实处理后，手动运行下一测试 cell 查看状态和字幕 sample，再运行独立清理 cell。测试上下文只记录本次规范化来源、精确 video ID 和唯一输出目录；未清理时拒绝启动下一次测试。

默认数据库路径是 `data/tubewatch.sqlite3`，调用者可以覆盖。项目保留 `data/` 目录，但 SQLite 文件属于本地持久运行状态，不进入版本控制。SQLite 错误统一转换为 `StateStorageError`，网络失败则不得创建或修改状态数据库。

## TubeScribe 外部依赖边界

TubeWatch 通过 Python 环境中正常安装的 `tubescribe` 包调用 `tubescribe.workflow.process_video`。适配模块把返回值转换为 TubeWatch 模型，把公开的 `WorkflowMembersOnlyError` 和“没有可下载的字幕”分别转换为专门的业务结果；缺少依赖和其他 workflow 失败仍转换为项目级错误。

TubeWatch 和 TubeScribe 不共享源码目录。文件系统位置、项目是否相邻、本地 checkout 名称都不属于集成契约。正式代码不得扫描兄弟目录、从 TubeScribe 的 `src` 路径导入、修改 `sys.path`、自动下载源码或自动执行 pip。editable install 只是把开发 checkout 安装为标准 Python 包的一种方式，安装之后与 GitHub、release 或其他合规来源的安装具有相同 import 语义。

单一模块 `src/tubewatch/integrations/tubescribe.py` 集中完成以下职责：

- 导入已安装的 TubeScribe 公开 Python API；
- 把 TubeWatch 视频 URL 交给 TubeScribe；
- 把返回值转换为 TubeWatch 自己的结果结构；
- 把 TubeScribe 异常转换为 TubeWatch 项目级异常。

TubeWatch 的 `process` CLI 调用自身 Python workflow；外部 TubeScribe CLI 仍只是次要备用方案。

执行 `process` 时如果包未安装，集成边界明确提示：`TubeScribe is not installed. Install TubeWatch with the TubeScribe integration dependency or install TubeScribe separately.` 不得静默查找本地目录或自动安装。
