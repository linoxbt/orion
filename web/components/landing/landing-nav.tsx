"use client";

import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { LogoMark } from "@/components/logo-mark";
import { HeaderAuth } from "@/components/auth/header-auth";

const LINKS: [string, string][] = [
  ["How it works", "/docs"],
  ["What it negotiates", "/#verticals"],
  ["Playbooks", "/docs#playbooks"],
  ["Dashboard", "/dashboard"],
  ["Billing", "/billing"],
];

/**
 * The menu glyph is not three equal bars: the middle bar runs near full width
 * while the top and bottom are shorter and centred, giving a tapered
 * silhouette. Drawn as rects at those proportions rather than three divs, so
 * the cross it becomes can share the same box.
 */
function MenuGlyph({ open }: { open: boolean }) {
  return (
    <span className="relative block h-[14px] w-[18px]" aria-hidden="true">
      <svg
        viewBox="0 0 22 16"
        className={`absolute inset-0 size-full transition-all duration-300 ${
          open ? "scale-75 opacity-0" : "scale-100 opacity-100"
        }`}
      >
        <rect x="5.33" y="0" width="10.67" height="2.67" rx="1.33" fill="currentColor" />
        <rect x="1.33" y="6.67" width="18.67" height="2.67" rx="1.33" fill="currentColor" />
        <rect x="5.33" y="13.33" width="10.67" height="2.67" rx="1.33" fill="currentColor" />
      </svg>
      <svg
        viewBox="0 0 16 16"
        className={`absolute inset-0 m-auto size-4 transition-all duration-300 ${
          open ? "scale-100 opacity-100" : "scale-75 opacity-0"
        }`}
      >
        <line x1="1" y1="1" x2="15" y2="15" strokeWidth="2" strokeLinecap="round" stroke="currentColor" />
        <line x1="15" y1="1" x2="1" y2="15" strokeWidth="2" strokeLinecap="round" stroke="currentColor" />
      </svg>
    </span>
  );
}

/**
 * Header plus a full-viewport takeover panel.
 *
 * The panel is glass rather than solid - a translucent fill over a heavy
 * backdrop blur - so whatever is behind it reads as a wash of colour and
 * never as legible text, while the panel's own content stays sharp. Links
 * arrive staggered rather than all at once.
 *
 * It is portaled to document.body rather than rendered inside <header>. The
 * header uses backdrop-blur, and per spec a backdrop-filter ancestor
 * establishes a containing block for fixed descendants exactly as transform
 * does - which would trap `fixed inset-0` inside the header's own height
 * instead of the viewport. Portaling escapes that entirely.
 */
export function LandingNav() {
  const [open, setOpen] = useState(false);
  const [mounted, setMounted] = useState(false);
  const pathname = usePathname();

  useEffect(() => {
    // document.body does not exist during SSR, and the first client render
    // must match the server's, so the portal mounts one render later.
    setMounted(true);
  }, []);

  useEffect(() => {
    setOpen(false);
  }, [pathname]);

  useEffect(() => {
    if (!open) return;

    // overflow:hidden locks scrolling but leaves the document's offset alone,
    // so on an already-scrolled page the panel can read as pinned near the top
    // of the document rather than centred in the visible viewport. Pinning the
    // body itself removes the ambiguity, and restoring the offset on close
    // puts the reader back exactly where they were.
    const scrollY = window.scrollY;
    const { style } = document.body;
    style.position = "fixed";
    style.top = `-${scrollY}px`;
    style.left = "0";
    style.right = "0";

    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") setOpen(false);
    }
    window.addEventListener("keydown", onKey);

    return () => {
      window.removeEventListener("keydown", onKey);
      style.position = "";
      style.top = "";
      style.left = "";
      style.right = "";
      window.scrollTo(0, scrollY);
    };
  }, [open]);

  return (
    <header className="sticky top-0 z-50 border-b border-[var(--l-line)] bg-[var(--l-bg)]/85 backdrop-blur-md">
      <nav
        aria-label="Main"
        className="mx-auto flex max-w-7xl items-center justify-between gap-6 px-5 py-4 sm:px-8"
      >
        <Link
          href="/"
          className="inline-flex items-center gap-2 text-[17px] font-semibold tracking-tight text-[var(--l-text)] transition-opacity hover:opacity-70"
        >
          <LogoMark className="h-[1.15em] w-[1.15em] text-[var(--l-accent)]" />
          <span className="whitespace-nowrap">
            OR<span className="text-[var(--l-accent)]">ION</span>
          </span>
        </Link>

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
            aria-label={open ? "Close menu" : "Open menu"}
            aria-expanded={open}
            className="flex size-10 shrink-0 items-center justify-center rounded-full border border-[var(--l-line-strong)] text-[var(--l-text)] transition-colors hover:border-[var(--l-text)]"
          >
            <MenuGlyph open={open} />
          </button>
        </div>
      </nav>

      {mounted &&
        createPortal(
          <div
            className={`fixed inset-0 z-[60] bg-[var(--l-bg)]/85 backdrop-blur-2xl transition-opacity duration-300 ${
              open ? "pointer-events-auto opacity-100" : "pointer-events-none opacity-0"
            }`}
            aria-hidden={!open}
          >
            <button
              type="button"
              onClick={() => setOpen(false)}
              aria-label="Close menu"
              tabIndex={open ? 0 : -1}
              className="absolute right-0 top-0 flex h-[68px] items-center px-5 sm:px-8"
            >
              <span className="flex size-10 items-center justify-center rounded-full border border-[var(--l-line-strong)] text-[var(--l-text)] transition-colors hover:border-[var(--l-text)]">
                <MenuGlyph open />
              </span>
            </button>

            <div className="flex h-full flex-col items-center justify-center gap-10 px-6 sm:gap-14">
              <div
                className={`flex items-center gap-3 ${open ? "animate-fade-rise" : ""}`}
                style={open ? { animationFillMode: "backwards" } : undefined}
              >
                <LogoMark className="h-9 w-9 text-[var(--l-accent)]" />
                <span className="text-2xl font-semibold tracking-tight text-[var(--l-text)]">
                  OR<span className="text-[var(--l-accent)]">ION</span>
                </span>
              </div>

              <nav aria-label="Menu" className="flex flex-col items-center gap-1 sm:gap-2">
                {LINKS.map(([label, href], i) => (
                  <Link
                    key={href}
                    href={href}
                    tabIndex={open ? 0 : -1}
                    onClick={() => setOpen(false)}
                    className={`text-[2rem] font-medium tracking-tight text-[var(--l-text)] transition-colors hover:text-[var(--l-accent)] sm:text-[3.4rem] ${
                      open ? "animate-fade-rise" : ""
                    }`}
                    style={
                      open
                        ? { animationDelay: `${(i + 1) * 60}ms`, animationFillMode: "backwards" }
                        : undefined
                    }
                  >
                    {label}
                  </Link>
                ))}
              </nav>

              <div
                className={`flex flex-col items-center gap-4 sm:hidden ${open ? "animate-fade-rise" : ""}`}
                style={open ? { animationDelay: "420ms", animationFillMode: "backwards" } : undefined}
              >
                <HeaderAuth />
              </div>
            </div>
          </div>,
          document.body,
        )}
    </header>
  );
}
