"use client";

const frontendBackendUrl = process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000";

export default function HomePage() {
  return (
    <main
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        minHeight: "100vh",
        padding: 24,
        background: "linear-gradient(135deg, #eff6ff 0%, #f9fafb 100%)",
        fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
        textAlign: "center",
      }}
    >
      <div
        style={{
          maxWidth: 480,
          width: "100%",
          background: "#ffffff",
          borderRadius: 16,
          padding: "40px 32px",
          boxShadow: "0 4px 24px rgba(0,0,0,0.06)",
          border: "1px solid #e5e7eb",
        }}
      >
        <div
          style={{
            width: 56,
            height: 56,
            borderRadius: 14,
            background: "#2563eb",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            margin: "0 auto 20px",
            fontSize: 24,
          }}
        >
          ✈️
        </div>

        <h1 style={{ margin: "0 0 8px", fontSize: 24, fontWeight: 700, color: "#111827" }}>
          Sky Secure Assistant
        </h1>
        <p style={{ margin: "0 0 28px", fontSize: 14, color: "#6b7280", lineHeight: 1.6 }}>
          Connect to the backend and start chatting with your Zoho Projects assistant.
        </p>

        <a
          href={`${frontendBackendUrl}/auth/login`}
          style={{
            display: "inline-flex",
            alignItems: "center",
            justifyContent: "center",
            gap: 8,
            width: "100%",
            padding: "14px 18px",
            borderRadius: 10,
            background: "#2563eb",
            color: "white",
            textDecoration: "none",
            fontSize: 15,
            fontWeight: 600,
            transition: "background 0.15s",
          }}
        >
          Login with Zoho
        </a>

        <p style={{ margin: "20px 0 0", fontSize: 12, color: "#9ca3af" }}>
          You'll be redirected to Zoho to authorize access to your Projects data.
        </p>
      </div>
    </main>
  );
}