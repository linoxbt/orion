"use client";

import { createContext, useContext, useState, type ReactNode } from "react";

type Theme = "light" | "dark";

interface ThemeState {
  theme: Theme;
  toggleTheme: () => void;
}

const ThemeContext = createContext<ThemeState | null>(null);

const STORAGE_KEY = "orion:theme";

/** Inline, run before hydration (see web/app/layout.tsx) so the first paint already has the right
 * data-theme attribute - avoids a flash of the wrong theme on load. Mirrors what next-themes does
 * internally; hand-rolled here since globals.css already keys off data-theme, not a `.dark` class. */
export const themeInitScript = `
(function () {
  try {
    var stored = window.localStorage.getItem("${STORAGE_KEY}");
    var theme = stored === "light" || stored === "dark"
      ? stored
      : (window.matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark");
    document.documentElement.setAttribute("data-theme", theme);
  } catch (e) {}
})();
`;

export function ThemeProvider({ children }: { children: ReactNode }) {
  // Lazy initializer so the client's first render already reflects the real theme (set
  // synchronously by themeInitScript before hydration) instead of always starting from a "dark"
  // guess and correcting a tick later in a useEffect - that correction was visible as a brief
  // theme-toggle icon flash (Sun shown briefly for light-theme users). SSR has no `document`, so
  // it still renders "dark" server-side; ThemeToggle marks its icon suppressHydrationWarning since
  // this specific client/server difference is expected and intentional, not a real mismatch bug.
  const [theme, setTheme] = useState<Theme>(() => {
    if (typeof document === "undefined") return "dark";
    const current = document.documentElement.getAttribute("data-theme");
    return current === "light" ? "light" : "dark";
  });

  function toggleTheme() {
    setTheme((prev) => {
      const next: Theme = prev === "light" ? "dark" : "light";
      document.documentElement.setAttribute("data-theme", next);
      window.localStorage.setItem(STORAGE_KEY, next);
      return next;
    });
  }

  return <ThemeContext.Provider value={{ theme, toggleTheme }}>{children}</ThemeContext.Provider>;
}

export function useTheme(): ThemeState {
  const ctx = useContext(ThemeContext);
  if (!ctx) throw new Error("useTheme must be used within a ThemeProvider");
  return ctx;
}
