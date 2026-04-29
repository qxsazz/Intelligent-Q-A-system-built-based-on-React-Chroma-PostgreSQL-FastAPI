import { FormEvent, useEffect, useState } from "react";

type FileItem = { id: string; file_name: string; chunk_count: number; created_at: string };
const API_BASE = "http://127.0.0.1:8000";

export function KnowledgeBasePage() {
  const [files, setFiles] = useState<FileItem[]>([]);
  const [selected, setSelected] = useState<File | null>(null);
  const [loading, setLoading] = useState(false);

  const refresh = async () => {
    const resp = await fetch(`${API_BASE}/kb/list`);
    if (!resp.ok) return;
    setFiles(await resp.json());
  };

  useEffect(() => {
    void refresh();
  }, []);

  const onUpload = async (e: FormEvent) => {
    e.preventDefault();
    if (!selected) return;
    setLoading(true);
    const fd = new FormData();
    fd.append("file", selected);
    await fetch(`${API_BASE}/kb/upload`, { method: "POST", body: fd });
    setSelected(null);
    await refresh();
    setLoading(false);
  };

  const onDelete = async (id: string) => {
    await fetch(`${API_BASE}/kb/${id}`, { method: "DELETE" });
    await refresh();
  };

  return (
    <div className="panel">
      <form onSubmit={onUpload} className="row">
        <input type="file" onChange={(e) => setSelected(e.target.files?.[0] ?? null)} />
        <button type="submit" disabled={loading || !selected}>{loading ? "Uploading..." : "Upload"}</button>
      </form>
      <h3>知识库文件</h3>
      <ul>
        {files.map((file) => (
          <li key={file.id}>
            {file.file_name} | chunks: {file.chunk_count} | uploaded: {new Date(file.created_at).toLocaleString()}
            <button onClick={() => onDelete(file.id)}>Delete</button>
          </li>
        ))}
      </ul>
    </div>
  );
}
