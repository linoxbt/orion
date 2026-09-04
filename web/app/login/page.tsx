"use client";

import { Suspense, useEffect } from "react";
import Link from "next/link";
import { Loading } from "@/components/loading";
import { useRouter, useSearchParams } from "next/navigation";
import { DynamicWidget, useDynamicContext, useIsLoggedIn } from "@dynamic-labs/sdk-react-core";
import { Wordmark } from "@/components/wordmark";
import { HeroWatermark } from "@/components/landing/hero-watermark";
import { siteHref } from "@/lib/site-urls";

const CONFIGURED = Boolean(process.env.NEXT_PUBLIC_DYNAMIC_ENVIRONMENT_ID);

function LoginPanel() {
  const isLoggedIn = useIsLoggedIn();
  const { sdkHasLoaded } = useDynamicContext();
  const router = useRouter();
  const params = useSearchParams();

  // Only ever redirect within this app - `next` comes from the query string,
  // so an absolute URL there would be an open redirect.
  const raw = params.get("next") ?? "/dashboard";
  const next = raw.startsWith("/") && !raw.startsWith("//") ? raw : "/dashboard";

  useEffect(() => {
    if (sdkHasLoaded && isLoggedIn) router.replace(next);
  }, [sdkHasLoaded, isLoggedIn, router, next]);

  if (!CONFIGURED) {
    return (
      <p className="rounded border border-line bg-surface-2 px-5 py-4 text-[13px] leading-relaxed text-ink-soft">
        Sign-in isn&rsquo;t configured on this deployment - {" "}
        <code className="font-mono text-[12px]">NEXT_PUBLIC_DYNAMIC_ENVIRONMENT_ID</code> is unset.
      </p>
    );
  }

  return (
    <div className="[&_button]:!rounded">
      <DynamicWidget />
    </div>
  );
}

export default function LoginPage() {
  return (
    <div className="grid min-h-screen lg:grid-cols-[1.05fr,0.95fr]">
      {/* Left: the reason to sign in at all. */}
      <section className="landing relative isolate hidden flex-col justify-between overflow-hidden border-r border-[var(--l-line)] px-12 py-12 lg:flex xl:px-16">
        <HeroWatermark />
        <Link href={siteHref("/")} className="relative z-10 transition-opacity hover:opacity-70">
          <Wordmark className="text-[1.2875rem]" />
        </Link>

        <div className="relative z-10 max-w-md">
          <h1 className="font-display text-display-sm leading-[1.1] text-[var(--l-text)] md:text-[2.6875rem]">
            Your bills, negotiated while you get on with your day.
          </h1>
          <p className="mt-6 text-[15px] leading-[1.7] text-[var(--l-muted)]">
          Upload a bill, authorise the call, follow it live.
        </p>
        </div>

        <p className="relative z-10 max-w-md text-[12px] leading-relaxed text-[var(--l-muted)]">
        Orion calls only once you authorise that specific bill, and says it is an AI.
      </p>
      </section>

      {/* Right: the actual door. */}
      <section className="flex flex-col justify-center px-6 py-16 sm:px-12 lg:px-16">
        <div className="mx-auto w-full max-w-sm">
          <Link href={siteHref("/")} className="mb-10 inline-block lg:hidden">
            <Wordmark className="text-[1.2875rem]" />
          </Link>

          <p className="font-mono text-[10px] uppercase tracking-[0.22em] text-muted">Welcome</p>
          <h2 className="mt-4 font-display text-[1.9375rem] leading-tight text-ink">Sign in to Orion</h2>
          <p className="mt-3 text-[14px] leading-relaxed text-ink-soft">
            Continue with your email address or a social account.
          </p>

          <div className="mt-9">
            <Suspense fallback={<Loading label="Preparing sign-in" className="py-8" />}>
              <LoginPanel />
            </Suspense>
          </div>

          <p className="mt-10 text-[12px] leading-relaxed text-muted">
            By continuing you agree that Orion may act as your authorised representative on calls
            you explicitly approve, and that those calls are recorded for verification.
          </p>
        </div>
      </section>
    </div>
  );
}
