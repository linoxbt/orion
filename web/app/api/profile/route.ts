import { NextResponse } from "next/server";

import { NotAuthenticated, requireUser, unauthorized } from "@/lib/auth";

const API_URL = process.env.API_URL ?? process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8080";

// Server-side only: holds ADMIN_API_KEY so it never reaches the browser bundle.
//
// The user id forwarded here is the one verified against Dynamic's JWKS above -
// never taken from the request body - so a crafted request cannot read or write
// somebody else's profile.
async function forward(request: Request, method: "GET" | "PUT") {
  let user;
  try {
    user = await requireUser(request);
  } catch (error) {
    if (error instanceof NotAuthenticated) return unauthorized(error.message);
    throw error;
  }

  const res = await fetch(`${API_URL}/api/profile`, {
    method,
    headers: {
      "X-Orion-Admin-Key": process.env.ADMIN_API_KEY ?? "",
      "X-Orion-User": user.id,
      // The backend verifies this itself; the header above is only a
      // fallback for deployments with no Dynamic environment configured.
      authorization: `Bearer ${user.token}`,
      "content-type": "application/json",
    },
    body: method === "PUT" ? JSON.stringify(await request.json()) : undefined,
  });

  return NextResponse.json(await res.json(), { status: res.status });
}

export async function GET(request: Request) {
  return forward(request, "GET");
}

export async function PUT(request: Request) {
  return forward(request, "PUT");
}
