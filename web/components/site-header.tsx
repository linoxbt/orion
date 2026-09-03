import Link from "next/link";
import { Wordmark } from "./wordmark";
import { ThemeToggle } from "./theme-toggle";
import { HeaderAuth } from "./auth/header-auth";

const LINKS = [
  { href: "/#how-it-works", label: "How it works" },
  { href: "/#verticals", label: "What we negotiate" },
];

export function SiteHeader() {
  return (
    <header className="sticky top-0 z-40 border-b border-line bg-paper/85 backdrop-blur-md">
      <nav
        aria-label="Site"
        className="mx-auto flex max-w-6xl items-center justify-between px-6 py-5 md:px-10"
      >
        <Link href="/" className="transition-opacity hover:opacity-70">
          <Wordmark className="text-[1.2875rem]" />
        </Link>

        <div className="flex items-center gap-7">
          {LINKS.map((link) => (
            <Link
              key={link.href}
              href={link.href}
              className="hidden text-[13px] text-ink-soft transition-colors hover:text-ink sm:inline"
            >
              {link.label}
            </Link>
          ))}
          <ThemeToggle />
          <HeaderAuth />
        </div>
      </nav>
    </header>
  );
}
