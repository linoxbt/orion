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
  async redirects() {
    return [
      { source: "/authorization", destination: "/docs/authorisation", permanent: true },
      { source: "/playbooks", destination: "/docs/playbooks", permanent: true },
    ];
  },
};

export default nextConfig;
