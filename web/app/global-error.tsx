"use client";

// Next.js requires global-error.tsx to render its own <html>/<body> - it replaces the root layout
// entirely, and only catches errors thrown by the root layout itself (a rare case, but the only
// gap app/error.tsx can't cover).
export default function GlobalError({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  return (
    <html lang="en">
      <body style={{ display: "flex", minHeight: "100vh", alignItems: "center", justifyContent: "center", fontFamily: "monospace" }}>
        <div style={{ textAlign: "center", maxWidth: 480, padding: 24 }}>
          <h1 style={{ fontSize: 20, fontWeight: 700 }}>Something broke.</h1>
          <p style={{ marginTop: 12, fontSize: 14, opacity: 0.75 }}>{error.message || "An unexpected error occurred."}</p>
          <button
            type="button"
            onClick={reset}
            style={{ marginTop: 24, padding: "8px 16px", borderRadius: 4, background: "#4d7cfd", color: "#0a0b0e", border: "none" }}
          >
            Try again
          </button>
        </div>
      </body>
    </html>
  );
}
