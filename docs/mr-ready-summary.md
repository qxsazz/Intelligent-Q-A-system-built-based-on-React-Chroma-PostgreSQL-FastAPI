# MR 提交说明（可直接使用）

## 已完成内容

- 基于 FastAPI 的全异步后端已完成，包含 RAG 管线与 SSE 流式输出。
- 已完成 PDF/TXT/MD 文档入库链路（解析、分块、向量化、持久化）。
- 已完成知识库接口（`upload`、`list`、`delete`）与历史记录接口（`list`、`detail`、`delete`）。
- 已完成前端问答页与知识库管理页。
- 已完成 PostgreSQL 持久化（文件、问答记录、召回来源）。
- 已完成结构化日志（request_id、耗时、检索统计、token 估算）。
- 已完成基础越狱防御规则与测试脚本。

## 环境说明

- 当前实现已切换为 Chroma 向量库。
- 在本机首次安装 Chroma 时，需要 Microsoft C++ Build Tools 来编译 `chroma-hnswlib`。
- 若其他机器安装失败，请先安装 [Microsoft C++ Build Tools](https://visualstudio.microsoft.com/visual-cpp-build-tools/)，再执行 `pip install chromadb==0.5.23`。

## Reviewer 本地启动命令

```bash
cd backend
python -m pip install -r requirements.txt
$env:PYTHONPATH='.'
python scripts/init_db.py
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

```bash
cd frontend
npm install
npm run dev -- --host 127.0.0.1 --port 5173
```

## 已验证结果（实测）

- `kb/upload` -> 200
- `kb/list` -> 200
- `chat/ask` SSE -> 200 (`sources/token/meta/done`)
- `history/list` -> 200
- `history/{id}` -> 200
- `kb/{file_id}` delete -> 200
- `backend /health` -> 200
- `frontend /` -> 200

## 截图清单

- 3 组问答截图（含来源）
- 流式打字机效果截图
- 知识库上传/列表/删除截图
- 历史记录列表/详情截图
- 结构化日志截图
- 越狱防御成功截图（`backend/scripts/jailbreak_test.py`）
