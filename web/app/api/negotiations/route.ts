import { NextResponse } from "next/server";

import { NotAuthenticated, requireUser, unauthorized } from "@/lib/auth";

const API_URL = process.env.API_URL ?? process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8080";

// Server-side only: holds ADMIN_API_KEY so it never reaches the browser bundle.
// Forwards to the backend's admin-key-gated GET /api/negotiations.
export async function GET(request: Request) {
  // The admin key below can place a real phone call and charge a real card, so
  // establish who is asking before using it. Verified against Dynamic's JWKS.
  let user;
  try {
    user = await requireUser(request);
  } catch (error) {
    if (error instanceof NotAuthenticated) return unauthorized(error.message);
    throw error;
  }

  const res = await fetch(`${API_URL}/api/negotiations`, {
    headers: {
      "X-Orion-Admin-Key": process.env.ADMIN_API_KEY ?? "",
      "X-Orion-User": user.id,
      // The backend verifies this itself; the header above is only a
      // fallback for deployments with no Dynamic environment configured.
      authorization: `Bearer ${user.token}`,
    },
  });

  const data = await res.json();
  return NextResponse.json(data, { status: res.status });
}
