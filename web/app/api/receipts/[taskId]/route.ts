import { NextResponse } from "next/server";

const API_URL = process.env.API_URL ?? process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8080";

/**
 * A shared receipt, proxied.
 *
 * Receipts are deliberately public - the point is a link somebody can send on
 * - so, as on the backend, there is no session check here. It is proxied for
 * the same reason as the playbooks: a browser fetch to another origin lives or
 * dies by that origin's CORS allowlist, and a shared link that works for the
 * sender and not the recipient is the worst version of that bug.
 */
export async function GET(
  _request: Request,
  { params }: { params: Promise<{ taskId: string }> }
) {
  const { taskId } = await params;
  const res = await fetch(`${API_URL}/api/receipts/${encodeURIComponent(taskId)}`);
  return NextResponse.json(await res.json(), { status: res.status });
}
