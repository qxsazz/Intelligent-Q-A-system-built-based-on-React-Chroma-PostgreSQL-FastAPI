import { useState } from "react";
import { ChatPage } from "./pages/ChatPage";
import { KnowledgeBasePage } from "./pages/KnowledgeBasePage";

export function App() {
  const [tab, setTab] = useState<"chat" | "kb">("chat");
  return (
    <div className="container app-shell">
      <header className="header">
        <h1>路觅智能问答助手</h1>
        <div className="tabs">
          <button onClick={() => setTab("chat")} className={tab === "chat" ? "active" : ""}>问答</button>
          <button onClick={() => setTab("kb")} className={tab === "kb" ? "active" : ""}>知识库</button>
        </div>
      </header>
      {tab === "chat" ? <ChatPage /> : <KnowledgeBasePage />}
    </div>
  );
}
