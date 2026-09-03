"use client";

import { Sun, Moon } from "lucide-react";
import { useTheme } from "./theme-provider";

export function ThemeToggle({ className = "" }: { className?: string }) {
  const { theme, toggleTheme } = useTheme();

  return (
    <button
      type="button"
      onClick={toggleTheme}
      aria-label={theme === "light" ? "Switch to dark theme" : "Switch to light theme"}
      className={`inline-flex h-8 w-8 items-center justify-center rounded-sm border border-line text-ink/75 transition hover:border-accent/50 hover:text-accent ${className}`}
    >
      {/* Server always renders "dark"'s icon (no document at SSR time); the client's lazy state
       * initializer (see theme-provider.tsx) may immediately know better (e.g. light theme) -
       * that's an intentional, expected difference, not a real hydration bug. */}
      <span suppressHydrationWarning>{theme === "light" ? <Moon size={16} /> : <Sun size={16} />}</span>
    </button>
  );
}
