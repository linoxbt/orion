import { NextResponse } from "next/server";

export async function GET() {
  const apiUrl = process.env.API_URL ?? process.env.NEXT_PUBLIC_API_URL ?? "";
  const key = process.env.ADMIN_API_KEY ?? "";
  try {
    const response = await fetch(`${apiUrl}/api/negotiations`, {
      headers: { "X-Orion-Admin-Key": key },
      cache: "no-store",
    });
    const body = await response.json();
    return NextResponse.json(
      {
        upstreamHost: new URL(apiUrl).host,
        adminKeyLength: key.length,
        upstreamStatus: response.status,
        upstreamDetail: body?.detail ?? null,
      },
      { headers: { "Cache-Control": "no-store" } },
    );
  } catch {
    return NextResponse.json({ upstreamHost: apiUrl ? new URL(apiUrl).host : null, adminKeyLength: key.length, upstreamStatus: null }, { status: 503 });
  }
}
