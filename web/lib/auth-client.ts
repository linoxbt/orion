import { getAuthToken } from "@dynamic-labs/sdk-react-core";

/** Every request to a gated proxy route carries the Dynamic session JWT.
 *
 * The proxy routes verify it against Dynamic's JWKS before attaching the admin
 * key, so a missing token means the request is refused rather than silently
 * served. */
export function authHeaders(extra: HeadersInit = {}): HeadersInit {
  const token = getAuthToken();
  return token ? { ...extra, authorization: `Bearer ${token}` } : extra;
}
