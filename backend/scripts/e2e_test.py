import json

import httpx


def run() -> None:
    with open("data/sample_kb.txt", "rb") as f:
        upload = httpx.post(
            "http://127.0.0.1:8000/kb/upload",
            files={"file": ("sample_kb.txt", f, "text/plain")},
            timeout=60,
        )
    print("upload_status", upload.status_code)
    print(upload.text)

    files_resp = httpx.get("http://127.0.0.1:8000/kb/list", timeout=30)
    print("kb_list_status", files_resp.status_code)
    print(files_resp.text)

    payload = {"question": "这个系统支持什么功能？", "session_id": "demo-1"}
    with httpx.stream("POST", "http://127.0.0.1:8000/chat/ask", json=payload, timeout=120) as stream_resp:
        print("chat_status", stream_resp.status_code)
        for line in stream_resp.iter_lines():
            if not line:
                continue
            print(line)

    history = httpx.get("http://127.0.0.1:8000/history/list", timeout=30)
    print("history_status", history.status_code)
    print(history.text)

    data = history.json()
    if data:
        rid = data[0]["id"]
        detail = httpx.get(f"http://127.0.0.1:8000/history/{rid}", timeout=30)
        print("history_detail_status", detail.status_code)
        print(detail.text[:500])

    kb_data = files_resp.json()
    if kb_data:
        fid = kb_data[0]["id"]
        deleted = httpx.delete(f"http://127.0.0.1:8000/kb/{fid}", timeout=30)
        print("kb_delete_status", deleted.status_code)
        print(deleted.text)


if __name__ == "__main__":
    run()
