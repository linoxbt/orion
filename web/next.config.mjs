/** @type {import('next').NextConfig} */
const nextConfig = {
  images: {
    // Real, properly-licensed photography (Unsplash License: free commercial
    // use, no attribution required) for the landing page's rotating hero
    // watermark - bills, statements and the paperwork this product is about.
    remotePatterns: [{ hostname: "images.unsplash.com" }],
  },

  /** Routes that moved into the docs.
   *
   * Declared here rather than as a page calling redirect(), because a page
   * redirect inside the App Router answers a direct request with 200 and a
   * NEXT_REDIRECT payload the browser acts on. That is fine for someone
   * clicking through the app and useless for a shared link, a crawler or
   * anything reading the status code. These answer 308 at the edge.
   */
  /** Security headers.
   *
   * Here rather than in netlify.toml, which was the first attempt and did
   * nothing: with the Next runtime, pages are rendered by a function and
   * Netlify's own header rules apply to statically served files. Next sets
   * these itself, on every response, which is verifiable - and was:
   * app.useorion.xyz was framable by any site on the internet, a page that
   * holds somebody's address, the last four digits of their SSN and the
   * button that phones a company on their behalf.
   *
   * The CSP stops at framing, form targets and base URIs on purpose. A
   * script-src worth having needs nonces threaded through Next's inline
   * bootstrap and Dynamic's widget loader; shipping a permissive one with
   * 'unsafe-inline' would only look like a policy.
   */
  async headers() {
    return [
      {
        source: "/:path*",
        headers: [
          {
            key: "Content-Security-Policy",
            value: "frame-ancestors 'none'; base-uri 'self'; form-action 'self'; object-src 'none'",
          },
          { key: "X-Frame-Options", value: "DENY" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          {
            key: "Permissions-Policy",
            value: "camera=(), geolocation=(), payment=(), microphone=(self)",
          },
        ],
      },
    ];
  },

  async redirects() {
    return [
      { source: "/authorization", destination: "/docs/authorisation", permanent: true },
      { source: "/playbooks", destination: "/docs/playbooks", permanent: true },
    ];
  },
};

export default nextConfig;
