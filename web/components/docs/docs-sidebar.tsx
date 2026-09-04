"use client";

import { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Menu, X } from "lucide-react";
import { DOCS, docPath } from "@/lib/docs-nav";
import { DocsSearch } from "./docs-search";

/**
 * The persistent left-hand navigation.
 *
 * Every page is listed, grouped, with the current one marked, so a reader
 * always knows where they are and what else exists. On a narrow screen it
 * collapses behind a button rather than disappearing: a docs site whose
 * contents are invisible on a phone is one nobody can navigate on a phone.
 */
export function DocsSidebar() {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);

  const list = (
    <nav aria-label="Documentation" className="flex flex-col gap-7">
      {DOCS.map((section) => (
        <div key={section.title}>
          <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted">
            {section.title}
          </p>
          <ul className="mt-3 flex flex-col gap-0.5">
            {section.pages.map((page) => {
              const href = docPath(page.slug);
              const active = pathname === href;
              return (
                <li key={page.slug || "overview"}>
                  <Link
                    href={href}
                    onClick={() => setOpen(false)}
                    aria-current={active ? "page" : undefined}
                    className={`-ml-3 block rounded px-3 py-1.5 text-[14px] leading-snug transition-colors ${
                      active
                        ? "bg-accent-soft font-medium text-accent"
                        : "text-ink-soft hover:bg-surface-2 hover:text-ink"
                    }`}
                  >
                    {page.title}
                  </Link>
                </li>
              );
            })}
          </ul>
        </div>
      ))}
    </nav>
  );

  return (
    <>
      <div className="mb-8 lg:hidden">
        <DocsSearch />
        <button
          type="button"
          onClick={() => setOpen((v) => !v)}
          aria-expanded={open}
          className="mt-4 flex items-center gap-2 rounded border border-line px-3.5 py-2 text-[13px] text-ink-soft transition-colors hover:border-ink hover:text-ink"
        >
          {open ? <X size={15} /> : <Menu size={15} />}
          Contents
        </button>
        {open && <div className="mt-6">{list}</div>}
      </div>

      <aside className="hidden lg:block">
        <div className="sticky top-24 flex flex-col gap-7">
          <DocsSearch />
          {list}
        </div>
      </aside>
    </>
  );
}
