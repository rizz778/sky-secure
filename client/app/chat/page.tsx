"use client";

import { useEffect, useMemo, useRef, useState } from "react";

const DEFAULT_SESSION = "default-session";
const DEFAULT_USER = "default-user";

interface PendingConfirmation {
  lastResponse: any;
  awaitingConfirmation: boolean;
}

export default function ChatPage() {
  const [message, setMessage] = useState("");
  const [history, setHistory] = useState<Array<{ role: string; content: string }>>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState<PendingConfirmation>({
    lastResponse: null,
    awaitingConfirmation: false,
  });
  const scrollRef = useRef<HTMLDivElement>(null);

  async function sendMessage() {
    if (!message.trim()) return;
    setError(null);
    setLoading(true);

    const userMessage = message.trim();
    setHistory((prev) => [...prev, { role: "user", content: userMessage }]);
    setMessage("");

    try {
      // Detect if this is a confirmation response
      let confirmation: boolean | undefined = undefined;
      if (pending.awaitingConfirmation) {
        const lowerMessage = userMessage.toLowerCase();
        if (lowerMessage === "yes" || lowerMessage === "y") {
          confirmation = true;
        } else if (lowerMessage === "no" || lowerMessage === "n") {
          confirmation = false;
        }
      }

      const requestBody: any = {
        message: userMessage,
        session_id: DEFAULT_SESSION,
        user_id: DEFAULT_USER,
      };

      // Include IDs from the last response if confirming (ensure strings)
      if (confirmation !== undefined && pending.lastResponse) {
        if (pending.lastResponse.portal_id != null) {
          requestBody.portal_id = String(pending.lastResponse.portal_id);
        }
        if (pending.lastResponse.project_id != null) {
          requestBody.project_id = String(pending.lastResponse.project_id);
        }
        if (pending.lastResponse.task_id != null) {
          requestBody.task_id = String(pending.lastResponse.task_id);
        }
        requestBody.confirmation = confirmation;
      }

      const response = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(requestBody),
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

      // Check if this response requires confirmation
      const requiresConfirmation = data?.confirmation_required === true && assistantText.includes("Confirm?");
      setPending({
        lastResponse: data,
        awaitingConfirmation: requiresConfirmation,
      });
    } catch (e) {
      setError((e as Error).message);
      setPending({ lastResponse: null, awaitingConfirmation: false });
    } finally {
      setLoading(false);
    }
  }

  function handleKeyDown(event: React.KeyboardEvent<HTMLInputElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      sendMessage();
    }
  }

  useEffect(() => {
    setError(null);
  }, [message]);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [history, loading]);

  return (
    <main
      style={{
        display: "flex",
        flexDirection: "column",
        height: "100vh",
        maxWidth: 760,
        margin: "0 auto",
        background: "#f9fafb",
        fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
      }}
    >
      <header
        style={{
          padding: "16px 20px",
          borderBottom: "1px solid #e5e7eb",
          background: "#ffffff",
        }}
      >
        <h1 style={{ margin: 0, fontSize: 18, fontWeight: 600 }}>Chat</h1>
        <p style={{ margin: "4px 0 0", fontSize: 12, color: "#9ca3af" }}>
          Session: {DEFAULT_SESSION} · User: {DEFAULT_USER}
        </p>
      </header>

      <div
        ref={scrollRef}
        style={{
          flex: 1,
          overflowY: "auto",
          padding: 20,
          display: "flex",
          flexDirection: "column",
          gap: 12,
        }}
      >
        {history.length === 0 ? (
          <div
            style={{
              margin: "auto",
              textAlign: "center",
              color: "#9ca3af",
              fontSize: 14,
            }}
          >
            Start the conversation by sending a message below.
          </div>
        ) : (
          history.map((item, index) => (
            <div
              key={index}
              style={{
                display: "flex",
                justifyContent: item.role === "user" ? "flex-end" : "flex-start",
              }}
            >
              <div
                style={{
                  maxWidth: "75%",
                  padding: "10px 14px",
                  borderRadius: 16,
                  fontSize: 14,
                  lineHeight: 1.5,
                  whiteSpace: "pre-wrap",
                  wordBreak: "break-word",
                  background: item.role === "user" ? "#2563eb" : "#ffffff",
                  color: item.role === "user" ? "#ffffff" : "#111827",
                  border: item.role === "user" ? "none" : "1px solid #e5e7eb",
                  boxShadow: item.role === "user" ? "none" : "0 1px 2px rgba(0,0,0,0.04)",
                }}
              >
                {item.content}
              </div>
            </div>
          ))
        )}

        {loading ? (
          <div style={{ display: "flex", justifyContent: "flex-start" }}>
            <div
              style={{
                padding: "10px 14px",
                borderRadius: 16,
                background: "#ffffff",
                border: "1px solid #e5e7eb",
                display: "flex",
                gap: 4,
                alignItems: "center",
              }}
            >
              {[0, 1, 2].map((i) => (
                <span
                  key={i}
                  style={{
                    width: 6,
                    height: 6,
                    borderRadius: "50%",
                    background: "#9ca3af",
                    animation: "bounce 1.4s infinite ease-in-out both",
                    animationDelay: `${i * 0.16}s`,
                  }}
                />
              ))}
            </div>
          </div>
        ) : null}
      </div>

      {error ? (
        <div
          style={{
            margin: "0 20px",
            padding: "8px 12px",
            borderRadius: 8,
            background: "#fef2f2",
            color: "#b91c1c",
            fontSize: 13,
            border: "1px solid #fecaca",
          }}
        >
          {error}
        </div>
      ) : null}

      <div
        style={{
          padding: 16,
          borderTop: "1px solid #e5e7eb",
          background: "#ffffff",
          display: "flex",
          gap: 10,
          alignItems: "center",
        }}
      >
        <input
          value={message}
          onChange={(event) => setMessage(event.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={
            loading
              ? "Sending..."
              : pending.awaitingConfirmation
              ? "Type 'Yes' or 'No' to confirm..."
              : "Type a message..."
          }
          disabled={loading}
          style={{
            flex: 1,
            padding: "12px 14px",
            borderRadius: 24,
            border: pending.awaitingConfirmation ? "2px solid #f59e0b" : "1px solid #d1d5db",
            background: loading ? "#f9fafb" : "white",
            fontSize: 14,
            outline: "none",
          }}
        />
        <button
          onClick={sendMessage}
          disabled={loading || !message.trim()}
          style={{
            padding: "12px 20px",
            borderRadius: 24,
            border: "none",
            background:
              loading || !message.trim()
                ? "#93c5fd"
                : pending.awaitingConfirmation
                ? "#f59e0b"
                : "#2563eb",
            color: "white",
            fontSize: 14,
            fontWeight: 500,
            cursor: loading || !message.trim() ? "not-allowed" : "pointer",
            transition: "background 0.15s",
          }}
        >
          {loading ? "Sending…" : pending.awaitingConfirmation ? "Confirm" : "Send"}
        </button>
      </div>

      <style jsx global>{`
        @keyframes bounce {
          0%, 80%, 100% { transform: scale(0.6); opacity: 0.4; }
          40% { transform: scale(1); opacity: 1; }
        }
      `}</style>
    </main>
  );
}