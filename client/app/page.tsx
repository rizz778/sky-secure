"use client";

const frontendBackendUrl = process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000";

export default function HomePage() {
  return (
    <main style={{ padding: 24, maxWidth: 720, margin: "0 auto" }}>
      <h1>Sky Secure Assistant</h1>
      <p>Connect to the backend and start chatting with your Zoho Projects assistant.</p>
      <a
        href={`${frontendBackendUrl}/auth/login`}
        style={{
          display: "inline-block",
          padding: "12px 18px",
          borderRadius: 8,
          background: "#2563eb",
          color: "white",
          textDecoration: "none",
        }}
      >
        Login with Zoho
      </a>
    </main>
  );
}
