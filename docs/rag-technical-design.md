# RAG 技术方案说明

## 1. 向量库选型

选型：**Chroma（本地持久化模式）**。

选型原因：

- 本地部署快速，适合 MVP 开发与演示。
- 支持 metadata 过滤，可按 `file_id` 删除向量。
- 数据落盘在 `VECTOR_PERSIST_DIR`，重启后可保留。

## 2. 文档分块策略

- 默认 `chunk_size = 700`
- 默认 `chunk_overlap = 100`
- 优先按标点/换行切分，降低语义断裂风险

每个 chunk 的 metadata：

- `file_id`
- `file_name`
- `chunk_index`
- `start_offset`
- `end_offset`
- `upload_time`

## 3. 检索参数

- 相似度检索 `top-k` 默认：`TOP_K=5`
- 返回结果包含来源文件和相似度分数

调优建议：

- 上下文不足时增大 `TOP_K`
- 回答过泛时减小 `chunk_size`
- 上下文衔接差时增大 `chunk_overlap`

## 4. Prompt 与安全策略

- Prompt 结构：系统安全指令 + 检索上下文 + 用户问题
- 基础越狱防御：
  - 对明显违规/恶意关键词进行拦截
  - 检索无命中时拒答并提示补充知识库

## 5. 数据持久化

PostgreSQL：

- `tjk_files`：上传文件元信息
- `tjk_qa_records`：问题、回答、会话、请求指标
- `tjk_qa_sources`：召回来源证据

向量库（Chroma）：

- 存储 chunk 向量及 metadata
- 支持按 `file_id` 删除，保证数据一致性

## 6. 可观测性

结构化 JSON 日志字段：

- `request_id`
- `latency_ms`
- `hit_count`
- `score_range`
- `prompt_tokens` / `completion_tokens`（估算）

## 7. 加分项策略

- 已实现：使用 `asyncio.Semaphore(5)` 进行 LLM 并发控制
- 可继续扩展：
  - 基于 `session_id` 的多轮上下文记忆
  - 混合检索（BM25 + 向量检索）
