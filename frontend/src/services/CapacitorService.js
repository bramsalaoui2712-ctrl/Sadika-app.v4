const API_BASE = (typeof process !== 'undefined' && process.env && process.env.REACT_APP_BACKEND_URL) || "http://127.0.0.1:8000";

export function streamChat(q, { provider="hybrid", model=null } = {}, onChunk) {
  const url = new URL(`${API_BASE}/api/chat/stream`);
  url.searchParams.set("q", q);
  url.searchParams.set("provider", provider);
  if (model) url.searchParams.set("model", model);

  const es = new EventSource(url.toString());
  es.onmessage = (ev) => {
    try {
      const data = JSON.parse(ev.data);
      if (data.type === "content" && onChunk) onChunk(data.text || "");
      if (data.type === "complete") es.close();
    } catch { /* noop */ }
  };
  es.onerror = () => es.close();
  return () => es.close();
}
