# TubeWatch 协作指南

- 修改前先阅读 `README.md` 和 `docs/` 中的文档。
- 不擅自扩大当前阶段范围；优先做小而可验证的改动。
- Notebook 必须调用 `src/tubewatch` 中的正式代码，不得复制实现逻辑。
- 不在仓库写入真实 Cookie、账号、私人频道 URL、登录信息、运行输出或执行计数。
- 未经真实验证的功能不得宣称可用；真实网络测试由用户在 Notebook 中主动运行。
- 不自动执行 Git commit 或 push。
- 不修改 TubeScribe 项目。
- TubeScribe 集成只能通过已安装包的公开 Python API；不得扫描兄弟目录、修改 `sys.path` 或改用源码路径。
- Notebook 中 `run_tubescribe` 默认保持 `False`；真实字幕处理必须由用户显式启用。
- 保持 Python 3.11+ 类型注解和简短公共 docstring，避免提前加入数据库、调度器或插件系统。
