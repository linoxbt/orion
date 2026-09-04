"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { Search } from "lucide-react";
import { DOC_ORDER, docPath } from "@/lib/docs-nav";

/**
 * Search across the documentation.
 *
 * Filters the page list rather than indexing prose: with a couple of dozen
 * pages, matching titles and summaries finds what someone means without
 * shipping a search index or calling a service. Cmd/Ctrl-K focuses it, which
 * is what anyone who reads documentation will try first.
 */
export function DocsSearch() {
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const inputRef = useRef<HTMLInputElement | null>(null);
  const router = useRouter();

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        inputRef.current?.focus();
      }
      if (e.key === "Escape") setOpen(false);
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const results = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return [];
    return DOC_ORDER.filter(
      (page) =>
        page.title.toLowerCase().includes(q) || page.summary.toLowerCase().includes(q),
    ).slice(0, 6);
  }, [query]);

  return (
    <div className="relative">
      <div className="flex items-center gap-2 rounded border border-line bg-surface px-3 py-2 focus-within:border-accent">
        <Search size={14} className="flex-none text-muted" />
        <input
          ref={inputRef}
          value={query}
          onChange={(e) => {
            setQuery(e.target.value);
            setOpen(true);
          }}
          onFocus={() => setOpen(true)}
          placeholder="Search the docs"
          aria-label="Search the documentation"
          className="w-full bg-transparent text-[13px] text-ink outline-none placeholder:text-muted"
        />
        <kbd className="hidden flex-none font-mono text-[10px] text-muted sm:block">&#8984;K</kbd>
      </div>

      {open && results.length > 0 && (
        <ul className="absolute z-20 mt-2 w-full overflow-hidden rounded border border-line bg-surface shadow-lg">
          {results.map((page) => (
            <li key={page.slug || "overview"}>
              <button
                type="button"
                onClick={() => {
                  router.push(docPath(page.slug));
                  setQuery("");
                  setOpen(false);
                }}
                className="block w-full border-b border-line px-4 py-3 text-left transition-colors last:border-b-0 hover:bg-surface-2"
              >
                <span className="block text-[13px] text-ink">{page.title}</span>
                <span className="mt-0.5 block text-[12px] leading-snug text-muted">
                  {page.summary}
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}

      {open && query.trim() && results.length === 0 && (
        <p className="absolute z-20 mt-2 w-full rounded border border-line bg-surface px-4 py-3 text-[13px] text-muted">
          Nothing matches that.
        </p>
      )}
    </div>
  );
}
