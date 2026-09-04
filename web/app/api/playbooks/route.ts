import { NextResponse } from "next/server";

const API_URL = process.env.API_URL ?? process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8080";

/**
 * The playbook list, proxied rather than fetched from the browser.
 *
 * It is public data - which desk to ask for, per vertical - so there is no
 * session to check. It goes through the server anyway because a call made
 * from the browser straight to the backend depends on that origin being in
 * the backend's CORS allowlist, and when the app moved onto app.useorion.xyz
 * it was not: the "what kind of account is this?" menu on /negotiate silently
 * came back empty. Nothing the browser calls should be able to break that way
 * again.
 */
export async function GET() {
  const res = await fetch(`${API_URL}/api/playbooks`, { next: { revalidate: 300 } });
  return NextResponse.json(await res.json(), { status: res.status });
}
