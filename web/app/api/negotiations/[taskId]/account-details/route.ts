import { NextResponse } from "next/server";

import { NotAuthenticated, requireUser, unauthorized } from "@/lib/auth";

const API_URL = process.env.API_URL ?? process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8080";

// Server-side only: holds ADMIN_API_KEY so it never reaches the browser bundle.
//
// This route carries the most sensitive data in the product - an account
// security PIN, the last four of an SSN - so it is write-only by design. The
// backend encrypts on receipt and never returns the values; GET here lists
// which fields are on file, names only.
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

  const res = await fetch(`${API_URL}/api/negotiations/${taskId}/account-details`, {
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

  const data = await res.json();
  return NextResponse.json(data, { status: res.status });
}

export async function GET(request: Request, { params }: { params: Promise<{ taskId: string }> }) {
  let user;
  try {
    user = await requireUser(request);
  } catch (error) {
    if (error instanceof NotAuthenticated) return unauthorized(error.message);
    throw error;
  }

  const { taskId } = await params;

  const res = await fetch(`${API_URL}/api/negotiations/${taskId}/account-details`, {
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
