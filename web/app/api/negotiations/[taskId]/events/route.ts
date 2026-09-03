import { NotAuthenticated, requireUser, unauthorized } from "@/lib/auth";

const API_URL = process.env.API_URL ?? process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8080";

// Server-side only: holds ADMIN_API_KEY so it never reaches the browser bundle.
// Proxies the backend's SSE feed of live call events. EventSource can't set
// headers, so this route is what lets the browser subscribe at all.
//
// The body is streamed straight through rather than awaited - buffering it
// would defeat the point, since the stream only ends when the call does.
export const dynamic = "force-dynamic";

export async function GET(request: Request, { params }: { params: Promise<{ taskId: string }> }) {
  // The admin key below can place a real phone call and charge a real card, so
  // establish who is asking before using it. Verified against Dynamic's JWKS.
  let user;
  try {
    user = await requireUser(request);
  } catch (error) {
    if (error instanceof NotAuthenticated) return unauthorized(error.message);
    throw error;
  }

  const { taskId } = await params;

  const upstream = await fetch(`${API_URL}/api/negotiations/${taskId}/events`, {
    headers: {
      "X-Orion-Admin-Key": process.env.ADMIN_API_KEY ?? "",
      "X-Orion-User": user.id,
      // The backend verifies this itself; the header above is only a
      // fallback for deployments with no Dynamic environment configured.
      authorization: `Bearer ${user.token}`,
    },
    // Propagates the browser closing the EventSource, so the backend drops its
    // subscriber instead of holding a queue open for a tab that's gone.
    signal: request.signal,
  });

  if (!upstream.ok || !upstream.body) {
    const detail = await upstream.text().catch(() => "");
    return new Response(detail || JSON.stringify({ detail: "event_stream_unavailable" }), {
      status: upstream.status,
      headers: { "content-type": "application/json" },
    });
  }

  return new Response(upstream.body, {
    headers: {
      "content-type": "text/event-stream",
      "cache-control": "no-cache, no-transform",
      connection: "keep-alive",
      "x-accel-buffering": "no",
    },
  });
}
