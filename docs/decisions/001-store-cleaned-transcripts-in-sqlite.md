# ADR 001：将清理后字幕正文存入 SQLite

## 状态

已接受。

## 背景

旧流程只在 `processing_records` 中保存 TubeScribe 产物路径，清理后正文仅存在于 TXT。TXT 容易被移动或单独修改，也无法与 `succeeded` 状态做原子一致性保证；同一视频出现在多个来源时，来源发现记录也不是合适的字幕所有者。

## 决定

建立全局 `videos` 表和独立 `transcripts` 表。`transcripts` 按 `(video_id, language_code, source_kind)` 保存一份当前 cleaned text、SHA-256、字符数、cleaner 元数据和 raw VTT 相对路径。`processing_records.transcript_id` 明确链接本次成功所对应的 transcript；保存正文和更新 `succeeded` 在同一 SQLite 事务中完成。

原始 VTT 留在文件系统，因为它是可人工检查、可重新清理的源文件，不适合把完整内容或未来可能出现的大型产物塞进状态数据库。TXT 保留为 TubeScribe 兼容产物或从数据库按需生成的导出格式，不再是可独立修改的权威数据源。

正文不放进 `videos`：视频元数据读取是高频轻量操作，正文体积大，而且一个视频未来可以有多语言、人工、自动或翻译字幕。独立表既避免普通视频查询加载大文本，也为将来的 transcript segments 和 FTS5 留出清晰边界。

## 后果

- SQLite 备份包含 cleaned text，但完整恢复原始材料仍需同时备份 raw VTT。
- 旧版没有 transcript 的 `succeeded` 记录迁回 `pending`，以维持成功必有正文的不变量。
- 当前不实现 segments 或 FTS5；未来可为 segment 建子表，或由 transcript 内容同步独立 FTS5 虚表，而不改变视频元数据表。
- 兼容 TXT 被删除或修改不会改变数据库中的权威正文。
