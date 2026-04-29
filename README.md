# 智能客服 Agent（MVP）

一个基于 RAG 的智能客服实习项目 MVP。

## 项目架构

- `backend`：FastAPI 全异步后端，包含 RAG、SSE 流式回答、数据库持久化。
- `frontend`：React + Vite 前端，包含问答页面与知识库管理页面。
- `backend/sql/init.sql`：PostgreSQL 初始化脚本。

## RAG 流程

1. 上传文档（`pdf/txt/md`）
2. 文档解析与分块（含重叠）
3. 调用 DashScope 生成 Embedding
4. 将向量与 metadata 写入 Chroma 本地持久化库
5. 按问题向量进行 Top-K 检索
6. 构造 Prompt 并通过 SSE 流式返回回答
7. 将问答与召回来源写入 PostgreSQL

## 环境变量

复制 `backend/.env.example` 为 `backend/.env`，并填写：

- `DASHSCOPE_API_KEY`
- `PG_DSN`
- `VECTOR_PERSIST_DIR`
- `UPLOAD_DIR`

请勿在源码中硬编码密钥或数据库密码。

## Quick Start（Reviewer）

### 0）前置依赖

- Python 3.10+
- Node.js 18+
- 可访问的 PostgreSQL
- Windows 首次安装 Chroma 如失败，请安装 [Microsoft C++ Build Tools](https://visualstudio.microsoft.com/visual-cpp-build-tools/)

### 1）后端（PowerShell）

```bash
cd backend
python -m pip install -r requirements.txt
$env:PYTHONPATH='.'
python scripts/init_db.py
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

### 1.1）后端（uv 一键方式，推荐）

```bash
cd backend
uv sync
uv run python scripts/init_db.py
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000
```

说明：

- `uv sync` 会按 `backend/pyproject.toml` 安装后端依赖
- 若未安装 `uv`，先执行：`pip install uv`

### 2）前端

```bash
cd frontend
npm install
npm run dev -- --host 127.0.0.1 --port 5173
```

### 3）快速验收

- 后端健康检查：`GET http://127.0.0.1:8000/health` 返回 200
- 前端页面：`http://127.0.0.1:5173` 可正常打开
- 核心链路：上传文件 -> 问答流式输出 -> 查看历史记录

## 本地运行（详细）

### 1）后端

```bash
cd backend
python -m venv .venv
.venv\\Scripts\\activate
python -m pip install -r requirements.txt
$env:PYTHONPATH='.'
python scripts/init_db.py
uvicorn app.main:app --reload --port 8000
```

### 2）初始化 PostgreSQL

已由 `python scripts/init_db.py` 覆盖（自动检查数据库并建表）。

### 3）前端

```bash
cd frontend
npm install
npm run dev
```

如果 PowerShell 中无法识别 `npm`，请安装 Node.js LTS 后重开终端。

## API 概览

### 问答接口

- `POST /chat/ask`
  - 请求体：`{ "question": "...", "session_id": "可选" }`
  - 返回：SSE 事件流（`token`、`sources`、`meta`、`done`）

### 知识库接口

- `POST /kb/upload`（multipart 文件上传）
- `GET /kb/list`
- `DELETE /kb/{file_id}`

### 历史记录接口

- `GET /history/list`
- `GET /history/{record_id}`
- `DELETE /history/{record_id}`

## 日志说明

结构化 JSON 日志包含：

- `request_id`
- `latency_ms`
- 检索命中数量与分数范围
- token 消耗估算

## 测试检查清单

- 成功上传并解析 `PDF/TXT/MD`
- 至少 3 个问答，且能显示召回来源片段
- 流式回答有明显增量输出效果
- 知识库上传、列表、删除功能正常
- 历史记录列表、详情、删除功能正常
- 日志中可看到 request_id、命中信息、耗时
