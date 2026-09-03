import { NextResponse } from "next/server";

import { NotAuthenticated, requireUser, unauthorized } from "@/lib/auth";

const API_URL = process.env.API_URL ?? process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8080";

// Which integrations are configured is operational detail. It used to be on
// the public /health endpoint, readable by anyone who curled the URL.
export async function GET(request: Request) {
  let user;
  try {
    user = await requireUser(request);
  } catch (error) {
    if (error instanceof NotAuthenticated) return unauthorized(error.message);
    throw error;
  }

  const res = await fetch(`${API_URL}/health/capabilities`, {
    headers: {
      "X-Orion-Admin-Key": process.env.ADMIN_API_KEY ?? "",
      "X-Orion-User": user.id,
      authorization: `Bearer ${user.token}`,
    },
  });

  return NextResponse.json(await res.json(), { status: res.status });
}
