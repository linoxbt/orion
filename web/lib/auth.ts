import { createRemoteJWKSet, jwtVerify } from "jose";

/** Server-side verification of a Dynamic session.
 *
 * Without this, "login" would be decoration: the proxy routes hold the admin
 * key that can place real phone calls and charge real money, so they must
 * establish who is asking before they use it. The JWT is signed by Dynamic and
 * verified here against their published JWKS - a token the browser forged
 * won't verify.
 */

const ENVIRONMENT_ID = process.env.NEXT_PUBLIC_DYNAMIC_ENVIRONMENT_ID ?? "";

const JWKS_URL = () =>
  new URL(`https://app.dynamic.xyz/api/v0/sdk/${ENVIRONMENT_ID}/.well-known/jwks`);

// Cached across requests: createRemoteJWKSet handles its own key rotation and
// caching, so this must not be rebuilt per call.
let jwks: ReturnType<typeof createRemoteJWKSet> | null = null;

function keySet() {
  if (!jwks) jwks = createRemoteJWKSet(JWKS_URL());
  return jwks;
}

export interface OrionUser {
  id: string;
  email?: string;
  /** The raw session token, forwarded to the backend so it can verify the
   * session itself rather than trusting this proxy's word for who is calling. */
  token: string;
}

export class NotAuthenticated extends Error {
  constructor(message = "not_authenticated") {
    super(message);
    this.name = "NotAuthenticated";
  }
}

function bearerFrom(request: Request): string | null {
  const header = request.headers.get("authorization");
  if (!header) return null;
  const [scheme, token] = header.split(" ");
  if (scheme?.toLowerCase() !== "bearer" || !token) return null;
  return token;
}

/** Verifies the caller's Dynamic JWT, or throws NotAuthenticated.
 *
 * Throws when the environment ID is unset too: an unconfigured deployment must
 * fail closed rather than silently let every request through. */
export async function requireUser(request: Request): Promise<OrionUser> {
  if (!ENVIRONMENT_ID) throw new NotAuthenticated("dynamic_not_configured");

  const token = bearerFrom(request);
  if (!token) throw new NotAuthenticated();

  try {
    const { payload } = await jwtVerify(token, keySet());
    const id = typeof payload.sub === "string" ? payload.sub : undefined;
    if (!id) throw new NotAuthenticated();
    return {
      id,
      email: typeof payload.email === "string" ? payload.email : undefined,
      token,
    };
  } catch (error) {
    if (error instanceof NotAuthenticated) throw error;
    throw new NotAuthenticated();
  }
}

/** The 401 body every gated proxy route returns, so the client can react to
 * one shape rather than guessing. */
export function unauthorized(detail = "not_authenticated") {
  return Response.json({ detail }, { status: 401 });
}
