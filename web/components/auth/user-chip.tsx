"use client";

import { useDynamicContext } from "@dynamic-labs/sdk-react-core";
import { LogOut } from "lucide-react";

/** Who is signed in, and the way out. Sits at the foot of the sidebar. */
export function UserChip({ collapsed = false }: { collapsed?: boolean }) {
  const { user, handleLogOut, sdkHasLoaded } = useDynamicContext();

  if (!sdkHasLoaded || !user) return null;

  const label = user.email ?? user.username ?? "Signed in";
  const initial = label.trim().charAt(0).toUpperCase() || "?";

  if (collapsed) {
    return (
      <button
        type="button"
        onClick={() => handleLogOut()}
        title={`Sign out (${label})`}
        aria-label={`Sign out (${label})`}
        className="flex h-8 w-8 items-center justify-center rounded-full bg-accent-soft text-[11px] font-medium text-accent transition-opacity hover:opacity-75"
      >
        {initial}
      </button>
    );
  }

  return (
    <div className="flex items-center gap-3 rounded border border-line px-3 py-2.5">
      <span className="flex h-7 w-7 flex-none items-center justify-center rounded-full bg-accent-soft text-[11px] font-medium text-accent">
        {initial}
      </span>
      <span className="min-w-0 flex-1 truncate text-[12px] text-ink-soft" title={label}>
        {label}
      </span>
      <button
        type="button"
        onClick={() => handleLogOut()}
        aria-label="Sign out"
        title="Sign out"
        className="flex-none text-muted transition-colors hover:text-fail"
      >
        <LogOut size={15} />
      </button>
    </div>
  );
}
