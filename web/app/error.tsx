"use client";

import Link from "next/link";
import { useEffect } from "react";

export default function GlobalError({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <div className="mx-auto flex min-h-screen max-w-lg flex-col items-center justify-center px-6 text-center">
      <p className="mb-3 font-mono text-[10px] uppercase tracking-[0.22em] text-fail">Something broke</p>
      <h1 className="font-display text-[1.8375rem]">This page hit an unexpected error.</h1>
      <p className="mt-3 text-sm leading-relaxed text-ink/70">
        {error.message || "An unexpected error occurred."}
      </p>
      <div className="mt-6 flex gap-4 font-mono text-sm">
        <button type="button" onClick={reset} className="rounded bg-accent px-4 py-2 text-accent-ink hover:bg-accent-hover">
          Try again
        </button>
        <Link href="/" className="rounded border border-line px-4 py-2 text-ink-soft hover:border-accent/50">
          Back to home
        </Link>
      </div>
    </div>
  );
}
