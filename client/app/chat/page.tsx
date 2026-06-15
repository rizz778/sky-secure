"use client";

import { useEffect, useMemo, useState } from "react";

const DEFAULT_SESSION = "default-session";
const DEFAULT_USER = "default-user";

export default function ChatPage() {
  const [message, setMessage] = useState("");
  const [history, setHistory] = useState<Array<{ role: string; content: string }>>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const summary = useMemo(() => history.map((item) => `${item.role}: ${item.content}`).join("\n"), [history]);

  async function sendMessage() {
    if (!message.trim()) return;
    setError(null);
    setLoading(true);

    const userMessage = message.trim();
    setHistory((prev) => [...prev, { role: "user", content: userMessage }]);
    setMessage("");

    try {
      const response = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: userMessage,
          session_id: DEFAULT_SESSION,
          user_id: DEFAULT_USER,
        }),
      });

      const bodyText = await response.text();
      let data: any = null;
      try {
        data = bodyText ? JSON.parse(bodyText) : null;
      } catch {
        data = { message: bodyText || response.statusText };
      }

      if (!response.ok) {
        throw new Error(data?.detail?.message || data?.message || response.statusText || "Chat request failed");
      }

      const assistantText = typeof data?.answer === "string" ? data.answer : String(data?.answer ?? "No reply");
      setHistory((prev) => [...prev, { role: "assistant", content: assistantText }]);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    setError(null);
  }, [message]);

  return (
    <main style={{ padding: 24, maxWidth: 920, margin: "0 auto" }}>
      <h1>Chat</h1>
      <div style={{ marginBottom: 24 }}>
        <strong>Session:</strong> default-session<br />
        <strong>User:</strong> default-user
      </div>
      <div style={{ marginBottom: 24 }}>
        <textarea
          rows={12}
          readOnly
          value={summary}
          style={{ width: "100%", borderRadius: 12, border: "1px solid #d1d5db", padding: 12, background: "#ffffff" }}
        />
      </div>
      <div style={{ display: "flex", gap: 12, marginBottom: 12, alignItems: "center" }}>
        <input
          value={message}
          onChange={(event) => setMessage(event.target.value)}
          placeholder={loading ? "Sending..." : "Type a message..."}
          disabled={loading}
          style={{
            flex: 1,
            padding: 12,
            borderRadius: 8,
            border: "1px solid #d1d5db",
            background: loading ? "#f9fafb" : "white",
          }}
        />
        <button
          onClick={sendMessage}
          disabled={loading || !message.trim()}
          style={{
            padding: "12px 18px",
            borderRadius: 8,
            border: "none",
            background: loading ? "#93c5fd" : "#2563eb",
            color: "white",
            cursor: loading ? "not-allowed" : "pointer",
          }}
        >
          {loading ? "Sending..." : "Send"}
        </button>
      </div>
      {loading ? (
        <p style={{ marginTop: 0, color: "#2563eb" }}>Waiting for assistant response…</p>
      ) : null}
      {error ? <p style={{ color: "#b91c1c" }}>{error}</p> : null}
    </main>
  );
}
