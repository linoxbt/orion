"use client";

import { useState } from "react";
import Link from "next/link";
import { Menu, X } from "lucide-react";
import { LogoMark } from "@/components/logo-mark";
import { HeaderAuth } from "@/components/auth/header-auth";

const LINKS: [string, string][] = [
  ["How it works", "/#how-it-works"],
  ["What it negotiates", "/#verticals"],
  ["Playbooks", "/playbooks"],
  ["Docs", "/docs"],
];

/** The landing page's own header.
 *
 * Separate from the app's SiteHeader, which is built for the light signed-in
 * surface and carries the theme toggle. This one is dark, sticky, and collapses
 * to a full-height sheet on small screens - a row of links that silently
 * disappears below the breakpoint is the usual way a "responsive" marketing
 * page turns out not to be.
 */
export function LandingNav() {
  const [open, setOpen] = useState(false);

  return (
    <header className="sticky top-0 z-50 border-b border-[var(--l-line)] bg-[var(--l-bg)]/85 backdrop-blur-md">
      <nav
        aria-label="Main"
        className="mx-auto flex max-w-7xl items-center justify-between gap-6 px-5 py-4 sm:px-8"
      >
        <Link
          href="/"
          onClick={() => setOpen(false)}
          className="inline-flex items-center gap-2 text-[17px] font-semibold tracking-tight text-[var(--l-text)] transition-opacity hover:opacity-70"
        >
          <LogoMark className="h-[1.15em] w-[1.15em] text-[var(--l-accent)]" />
          <span className="whitespace-nowrap">
            OR<span className="text-[var(--l-accent)]">ION</span>
          </span>
        </Link>

        <div className="hidden items-center gap-8 lg:flex">
          {LINKS.map(([label, href]) => (
            <Link
              key={href}
              href={href}
              className="text-[14px] text-[var(--l-muted)] transition-colors hover:text-[var(--l-text)]"
            >
              {label}
            </Link>
          ))}
        </div>

        <div className="flex items-center gap-3">
          <div className="hidden sm:block">
            <HeaderAuth />
          </div>
          <Link
            href="/negotiate"
            className="hidden rounded-full bg-[var(--l-accent)] px-5 py-2.5 text-[13px] font-medium text-[#131416] transition-colors hover:bg-[var(--l-accent-hover)] sm:inline-flex"
          >
            Start
          </Link>
          <button
            type="button"
            onClick={() => setOpen((v) => !v)}
            aria-expanded={open}
            aria-label={open ? "Close menu" : "Open menu"}
            className="-mr-1 p-2 text-[var(--l-text)] lg:hidden"
          >
            {open ? <X size={20} /> : <Menu size={20} />}
          </button>
        </div>
      </nav>

      {open && (
        <div className="border-t border-[var(--l-line)] bg-[var(--l-bg)] lg:hidden">
          <div className="mx-auto flex max-w-7xl flex-col px-5 py-3 sm:px-8">
            {LINKS.map(([label, href]) => (
              <Link
                key={href}
                href={href}
                onClick={() => setOpen(false)}
                className="border-b border-[var(--l-line)] py-4 text-[16px] text-[var(--l-text)] last:border-b-0"
              >
                {label}
              </Link>
            ))}
            <div className="flex flex-col gap-3 py-5 sm:hidden">
              <HeaderAuth />
              <Link
                href="/negotiate"
                onClick={() => setOpen(false)}
                className="rounded-full bg-[var(--l-accent)] px-5 py-3 text-center text-[14px] font-medium text-[#131416]"
              >
                Start a negotiation
              </Link>
            </div>
          </div>
        </div>
      )}
    </header>
  );
}
