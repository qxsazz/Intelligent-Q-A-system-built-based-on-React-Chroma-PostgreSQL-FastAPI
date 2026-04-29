import { FormEvent, useEffect, useRef, useState } from "react";
import { marked } from "marked";

type SourceHit = {
  content: string;
  score: number;
  metadata?: { file_name?: string; file_id?: string; chunk_index?: number };
};
type HistoryItem = { id: string; question: string; created_at: string; session_id?: string | null };
type SessionSummary = { sessionId: string; latestRecordId?: string; latestQuestion?: string; latestCreatedAt?: string };
type SessionTurn = { id: string; question: string; answer: string; created_at: string };
type ChatTurn = { id: string; question: string; answer: string; sources: SourceHit[] };

const API_BASE = "http://127.0.0.1:8000";

export function ChatPage() {
  const chatScrollRef = useRef<HTMLDivElement | null>(null);
  const [sessionId, setSessionId] = useState(() => {
    const existing = localStorage.getItem("chat_session_id");
    if (existing) return existing;
    const created = crypto.randomUUID();
    localStorage.setItem("chat_session_id", created);
    return created;
  });
  const [question, setQuestion] = useState("");
  const [chatTurns, setChatTurns] = useState<ChatTurn[]>([]);
  const [history, setHistory] = useState<HistoryItem[]>([]);
  const [draftSessions, setDraftSessions] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);

  const refreshHistory = async () => {
    const resp = await fetch(`${API_BASE}/history/list`);
    if (!resp.ok) return;
    setHistory(await resp.json());
  };

  const sessionOptions = Array.from(
    new Set(history.map((item) => item.session_id).filter((sid): sid is string => Boolean(sid)))
  );

  const sessionSummaries = (() => {
    const latestBySession = new Map<string, SessionSummary>();
    for (const item of history) {
      const sid = item.session_id;
      if (!sid) continue;
      if (!latestBySession.has(sid)) {
        latestBySession.set(sid, {
          sessionId: sid,
          latestRecordId: item.id,
          latestQuestion: item.question,
          latestCreatedAt: item.created_at,
        });
      }
    }
    for (const sid of draftSessions) {
      if (!latestBySession.has(sid)) {
        latestBySession.set(sid, { sessionId: sid });
      }
    }
    if (!latestBySession.has(sessionId)) {
      latestBySession.set(sessionId, { sessionId });
    }
    return Array.from(latestBySession.values()).sort((a, b) => {
      if (a.sessionId === sessionId) return -1;
      if (b.sessionId === sessionId) return 1;
      const ta = a.latestCreatedAt ? new Date(a.latestCreatedAt).getTime() : 0;
      const tb = b.latestCreatedAt ? new Date(b.latestCreatedAt).getTime() : 0;
      return tb - ta;
    });
  })();

  const loadSessionTurns = async (sid: string) => {
    const resp = await fetch(`${API_BASE}/history/session/${encodeURIComponent(sid)}`);
    if (!resp.ok) return;
    const rows: SessionTurn[] = await resp.json();
    setChatTurns(
      rows.map((row) => ({
        id: row.id,
        question: row.question,
        answer: row.answer,
        sources: [],
      }))
    );
  };

  useEffect(() => {
    void refreshHistory();
  }, []);

  useEffect(() => {
    void loadSessionTurns(sessionId);
  }, [sessionId]);

  useEffect(() => {
    const el = chatScrollRef.current;
    if (!el) return;
    el.scrollTop = el.scrollHeight;
  }, [chatTurns, loading]);

  const startNewSession = () => {
    const created = crypto.randomUUID();
    localStorage.setItem("chat_session_id", created);
    setSessionId(created);
    setDraftSessions((prev) => (prev.includes(created) ? prev : [created, ...prev]));
    setChatTurns([]);
  };

  const switchSession = (sid: string) => {
    localStorage.setItem("chat_session_id", sid);
    setSessionId(sid);
    setChatTurns([]);
  };

  const clearCurrentSession = async () => {
    await fetch(`${API_BASE}/history/session/${encodeURIComponent(sessionId)}`, { method: "DELETE" });
    setChatTurns([]);
    await refreshHistory();
  };

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    const currentQuestion = question.trim();
    if (!currentQuestion) return;

    const turnId = crypto.randomUUID();
    setChatTurns((prev) => [...prev, { id: turnId, question: currentQuestion, answer: "", sources: [] }]);
    setLoading(true);
    setQuestion("");

    const resp = await fetch(`${API_BASE}/chat/ask`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question: currentQuestion, session_id: sessionId })
    });
    if (!resp.ok) {
      setLoading(false);
      setChatTurns((prev) =>
        prev.map((turn) => (turn.id === turnId ? { ...turn, answer: `请求失败：${resp.status}` } : turn))
      );
      return;
    }
    const reader = resp.body?.getReader();
    if (!reader) {
      setLoading(false);
      return;
    }
    const decoder = new TextDecoder("utf-8");
    let buffer = "";
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const normalized = buffer.replace(/\r\n/g, "\n");
      const chunks = normalized.split("\n\n");
      buffer = chunks.pop() ?? "";
      for (const raw of chunks) {
        const lines = raw.split("\n");
        const eventLine = lines.find((line) => line.startsWith("event:"));
        const dataLine = lines.find((line) => line.startsWith("data:"));
        if (!eventLine || !dataLine) continue;
        const event = eventLine.slice("event:".length).trim();
        const payload = dataLine.slice("data:".length).trim();
        let data: unknown;
        try {
          data = JSON.parse(payload);
        } catch {
          continue;
        }
        if (event === "token") {
          if (typeof data === "string") {
            setChatTurns((prev) =>
              prev.map((turn) => (turn.id === turnId ? { ...turn, answer: `${turn.answer}${data}` } : turn))
            );
          } else if (Array.isArray(data)) {
            const next = data.join("");
            setChatTurns((prev) =>
              prev.map((turn) => (turn.id === turnId ? { ...turn, answer: `${turn.answer}${next}` } : turn))
            );
          }
        }
        if (event === "sources" && Array.isArray(data)) {
          setChatTurns((prev) =>
            prev.map((turn) => (turn.id === turnId ? { ...turn, sources: data as SourceHit[] } : turn))
          );
        }
      }
    }
    setLoading(false);
    await refreshHistory();
    setDraftSessions((prev) => prev.filter((sid) => sid !== sessionId));
  };

  const openSourceFile = (item: SourceHit) => {
    const fileId = item.metadata?.file_id;
    if (!fileId) return;
    const chunkIndex = item.metadata?.chunk_index;
    const query = typeof chunkIndex === "number" ? `?chunk_index=${encodeURIComponent(String(chunkIndex))}` : "";
    window.open(`${API_BASE}/kb/file/${encodeURIComponent(fileId)}/preview${query}`, "_blank", "noopener,noreferrer");
  };

  return (
    <div className="chat-layout">
      <aside className="chat-sidebar">
        <div className="sidebar-head">
          <button type="button" onClick={startNewSession} disabled={loading}>
            + 新建对话
          </button>
          <button type="button" onClick={() => void clearCurrentSession()} disabled={loading}>
            清空会话
          </button>
        </div>
        <div className="session-tools">
          <label>会话选择</label>
          <select value={sessionId} onChange={(e) => void switchSession(e.target.value)} disabled={loading}>
            <option value={sessionId}>当前会话</option>
            {sessionOptions
              .filter((sid) => sid !== sessionId)
              .map((sid) => (
                <option key={sid} value={sid}>
                  {sid}
                </option>
              ))}
          </select>
          <div className="session-id">Session: {sessionId}</div>
        </div>
        <h3>当前对话记录</h3>
        <ul className="history-list">
          {sessionSummaries.map((item) => (
            <li key={item.sessionId} className="history-item">
              <button
                type="button"
                className="history-title"
                onClick={() => {
                  switchSession(item.sessionId);
                  void loadSessionTurns(item.sessionId);
                }}
              >
                {item.latestQuestion ?? "（新建会话，暂无消息）"}
              </button>
              <button
                type="button"
                className="history-del"
                disabled={!item.latestRecordId}
                onClick={() => void loadSessionTurns(item.sessionId)}
              >
                详情
              </button>
            </li>
          ))}
        </ul>
      </aside>
      <section className="chat-main">
        <div className="answer-wrapper" ref={chatScrollRef}>
          <div className="chat-stream">
            <h3>对话</h3>
            <div className="chat-turns">
            {chatTurns.map((turn) => (
              <div key={turn.id} className="turn-group">
                <div className="turn user-turn">
                  <div className="turn-role">
                    <span className="role-badge user-badge">🙂</span>
                    你
                  </div>
                  <div className="turn-bubble">{turn.question}</div>
                </div>
                <div className="turn assistant-turn">
                  <div className="turn-role">
                    <span className="role-badge assistant-badge">🤖</span>
                    助手
                  </div>
                  <div
                    className="turn-bubble markdown"
                    dangerouslySetInnerHTML={{ __html: marked.parse(turn.answer || (loading ? "..." : "")) }}
                  />
                  {turn.sources.length > 0 && (
                    <ul className="source-list">
                      {turn.sources.map((item, idx) => (
                        <li key={`${turn.id}-${idx}`}>
                          {item.metadata?.file_name ?? "unknown"}{" "}
                          <button type="button" onClick={() => openSourceFile(item)} disabled={!item.metadata?.file_id}>
                            打开片段
                          </button>{" "}
                          | score: {item.score.toFixed(4)}
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              </div>
            ))}
            {!chatTurns.length && <div className="empty-chat">开始提问后，这里会按轮次显示你的问题和助手回答。</div>}
            </div>
          </div>
        </div>
        <form onSubmit={onSubmit} className="chat-input-bar">
          <div className="chat-input-row">
            <input value={question} onChange={(e) => setQuestion(e.target.value)} placeholder="输入你的问题..." />
            <button type="submit" disabled={loading || !question.trim()}>
              {loading ? "生成中..." : "发送"}
            </button>
          </div>
        </form>
      </section>
    </div>
  );
}
