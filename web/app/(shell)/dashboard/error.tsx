"use client";

import { useEffect } from "react";

export default function DashboardError({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <div className="rounded border border-fail/40 bg-fail/10 px-6 py-10 text-center">
      <p className="font-display text-[1.3875rem] text-fail">This page hit an unexpected error</p>
      <p className="mx-auto mt-2 max-w-md text-sm leading-relaxed text-ink/70">
        {error.message || "An unexpected error occurred rendering the dashboard."}
      </p>
      <button
        type="button"
        onClick={reset}
        className="mt-4 rounded bg-accent px-4 py-2 text-[13px] font-medium text-accent-ink hover:bg-accent-hover"
      >
        Try again
      </button>
    </div>
  );
}
