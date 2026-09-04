import { NextResponse, type NextRequest } from "next/server";

/**
 * One deployment, three front doors.
 *
 *   useorion.xyz        the landing page
 *   docs.useorion.xyz   the documentation
 *   app.useorion.xyz    the signed-in product
 *
 * Netlify serves every hostname from the same site, so the hostname is what
 * decides which part of the app a visitor is looking at. This rewrites rather
 * than redirects: the address bar keeps saying docs.useorion.xyz while the
 * page underneath is /docs, which is the point of having the subdomain at all.
 *
 * Only the *root* of each subdomain is rewritten. Deeper paths are left alone
 * so that docs.useorion.xyz/dashboard still works rather than 404ing, and so
 * every asset, API route and Next.js internal keeps resolving normally on all
 * three hosts.
 */

/** Where the root of each hostname actually lives. */
const HOME: Record<string, string> = {
  docs: "/docs",
  app: "/dashboard",
};

/**
 * Hostnames that own a whole section of the app rather than just a landing
 * spot. On docs.useorion.xyz every path is a documentation path, so the
 * "/docs" prefix is noise in the address bar: the hostname already said it.
 */
const SECTION_PREFIX: Record<string, string> = {
  docs: "/docs",
};

function subdomainOf(host: string): string | null {
  // Strip the port a local or preview host may carry.
  const name = host.split(":")[0].toLowerCase();
  if (!name.endsWith(".useorion.xyz")) return null;
  const label = name.slice(0, -".useorion.xyz".length);
  // "www" is the apex under another name, not a section of the product.
  return label === "www" ? null : label;
}

export function middleware(request: NextRequest) {
  const host = request.headers.get("host") ?? "";
  const sub = subdomainOf(host);
  if (!sub) return NextResponse.next();

  const home = HOME[sub];
  if (!home) return NextResponse.next();

  const { pathname } = request.nextUrl;
  const prefix = SECTION_PREFIX[sub];

  if (prefix) {
    // The prefix is redundant on this hostname, so send it to the clean form
    // once rather than serving the same page at two addresses.
    if (pathname === prefix || pathname.startsWith(`${prefix}/`)) {
      const url = request.nextUrl.clone();
      url.pathname = pathname.slice(prefix.length) || "/";
      return NextResponse.redirect(url, 308);
    }

    // Everything else on this hostname is that section, rewritten so the
    // address bar keeps the short URL the reader actually typed.
    const url = request.nextUrl.clone();
    url.pathname = pathname === "/" ? prefix : `${prefix}${pathname}`;
    return NextResponse.rewrite(url);
  }

  // Hostnames with only a landing spot: the root goes there, anything deeper
  // is already a real path on this app.
  if (pathname !== "/") return NextResponse.next();

  const url = request.nextUrl.clone();
  url.pathname = home;
  return NextResponse.rewrite(url);
}

export const config = {
  /**
   * Skip everything that is not a page: Next.js internals, the API routes the
   * app talks to, and any file with an extension. Running this on every asset
   * request would cost a middleware invocation per image for no benefit.
   */
  matcher: ["/((?!_next/|api/|.*\\.[\\w]+$).*)"],
};
