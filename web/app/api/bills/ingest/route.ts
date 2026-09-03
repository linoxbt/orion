import { NotAuthenticated, requireUser, unauthorized } from "@/lib/auth";

const API_URL = process.env.API_URL ?? process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8080";

// Bill extraction used to be called cross-origin straight from the browser,
// which meant two problems: it depended on CORS, and a 500 from the backend
// arrives without CORS headers - so the browser couldn't read the error and
// reported a bare "Failed to fetch" instead of what actually went wrong.
//
// Proxying it same-origin removes CORS from the picture and gates it:
// extraction spends Gemini quota on every call and was open to anyone who
// found the URL.
//
// Netlify's function limit sits well below 60s on standard plans, so the
// upstream call is given a deadline just inside it. Without one, a slow
// extraction fails at the proxy even when the backend eventually succeeds -
// surfacing as the same opaque failure the backend already worked hard to
// explain.
export const maxDuration = 26;
const UPSTREAM_TIMEOUT_MS = 24_000;

export async function POST(request: Request) {
  let user;
  try {
    user = await requireUser(request);
  } catch (error) {
    if (error instanceof NotAuthenticated) return unauthorized(error.message);
    throw error;
  }

  const incoming = await request.formData();
  const file = incoming.get("file");
  if (!(file instanceof Blob)) {
    return Response.json({ detail: "no_file" }, { status: 422 });
  }

  const forwarded = new FormData();
  // The filename is what the backend derives the MIME type from - browsers
  // report application/octet-stream for a .PDF often enough to matter.
  forwarded.append("file", file, incoming.get("filename")?.toString() ?? "bill");

  let res: Response;
  try {
    res = await fetch(`${API_URL}/api/bills/ingest`, {
      method: "POST",
      signal: AbortSignal.timeout(UPSTREAM_TIMEOUT_MS),
      headers: {
        "X-Orion-Admin-Key": process.env.ADMIN_API_KEY ?? "",
        "X-Orion-User": user.id,
        // The backend verifies this itself; the header above is only a
        // fallback for deployments with no Dynamic environment configured.
        authorization: `Bearer ${user.token}`,
      },
      body: forwarded,
    });
  } catch {
    // A timeout here is the extraction outlasting the platform's limit, which
    // is the same situation the backend calls "busy" - so say that, rather
    // than leaving the caller with a dead request and no explanation.
    return Response.json(
      { detail: "extraction_busy: that took too long, try again shortly" },
      { status: 503 }
    );
  }

  // Pass the backend's own status and detail through, so the UI can say "the
  // model is busy, try again" rather than a generic failure.
  const text = await res.text();
  return new Response(text, {
    status: res.status,
    headers: { "content-type": res.headers.get("content-type") ?? "application/json" },
  });
}
