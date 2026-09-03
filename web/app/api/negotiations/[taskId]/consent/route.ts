import { NextResponse } from "next/server";

import { NotAuthenticated, requireUser, unauthorized } from "@/lib/auth";

const API_URL = process.env.API_URL ?? process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8080";

// Server-side only: holds ADMIN_API_KEY so it never reaches the browser bundle.
// Records in-app authorisation to act as the customer's representative, which
// is what unlocks placing the call.
export async function POST(request: Request, { params }: { params: Promise<{ taskId: string }> }) {
  let user;
  try {
    user = await requireUser(request);
  } catch (error) {
    if (error instanceof NotAuthenticated) return unauthorized(error.message);
    throw error;
  }

  const { taskId } = await params;
  const body = await request.json();

  const res = await fetch(`${API_URL}/api/negotiations/${taskId}/consent`, {
    method: "POST",
    headers: {
      "X-Orion-Admin-Key": process.env.ADMIN_API_KEY ?? "",
      "X-Orion-User": user.id,
      // The backend verifies this itself; the header above is only a
      // fallback for deployments with no Dynamic environment configured.
      authorization: `Bearer ${user.token}`,
      "content-type": "application/json",
    },
    body: JSON.stringify(body),
  });

  return NextResponse.json(await res.json(), { status: res.status });
}
