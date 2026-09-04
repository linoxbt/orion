import { redirect } from "next/navigation";

/** Folded into the docs.
 *
 * This page only ever explained what authorising a call means, which is the
 * docs page's job. Kept as a redirect rather than deleted, because the link
 * has been given out and a dead URL is worse than a moved one.
 */
export default function AuthorizationPage() {
  redirect("/docs#authorisation");
}
