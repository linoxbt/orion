/**
 * One product, three hostnames.
 *
 *   useorion.xyz        the landing page
 *   docs.useorion.xyz   the documentation
 *   app.useorion.xyz    the signed-in product
 *
 * Every one of them is served by this same deployment, so a plain relative
 * href works everywhere - it just keeps the reader on whichever hostname they
 * arrived at, which makes the three read as three different sites. These
 * helpers send a link to the host that section actually belongs to.
 *
 * When no root domain is configured - local development, a Netlify preview,
 * the bare netlify.app URL - they fall back to relative paths, so nothing
 * points at a domain that is not serving the code being worked on.
 */

const ROOT = process.env.NEXT_PUBLIC_ROOT_DOMAIN ?? "";

function on(subdomain: "" | "app" | "docs", path: string): string {
  const clean = path.startsWith("/") ? path : `/${path}`;
  if (!ROOT) return clean;
  const host = subdomain ? `${subdomain}.${ROOT}` : ROOT;
  return `https://${host}${clean === "/" ? "" : clean}`;
}

/** The marketing site: the landing page and anything alongside it. */
export const siteHref = (path = "/") => on("", path);

/** The signed-in product: dashboard, negotiations, billing, account. */
export const appHref = (path = "/") => on("app", path);

/** The documentation. */
export const docsHref = (path = "/") => on("docs", path);

/**
 * True when the three hostnames are actually in play. Used to decide whether
 * a link needs to leave the current host at all.
 */
export const hasSubdomains = Boolean(ROOT);
