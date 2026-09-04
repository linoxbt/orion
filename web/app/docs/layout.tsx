import Link from "next/link";
import { LogoMark } from "@/components/logo-mark";
import { ThemeToggle } from "@/components/theme-toggle";

/** Docs are public.
 *
 * This page explains what the product does and is the landing page's main call
 * to action. Inside the signed-in shell it sat behind AuthGate, so a stranger
 * who clicked "How it works" to find out what Orion is got a login form -
 * being asked to create an account to read the explanation of why they might
 * want one.
 *
 * It keeps the app's own palette rather than the landing page's dark one: the
 * content is written against the reading tokens, and the landing tokens only
 * exist inside `.landing`, so borrowing that chrome would render dark text on
 * a dark ground.
 */
export default function DocsLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen bg-paper">
      <header className="sticky top-0 z-40 border-b border-line bg-paper/85 backdrop-blur-md">
        <nav
          aria-label="Docs"
          className="mx-auto flex max-w-3xl items-center justify-between gap-4 px-5 py-4 sm:px-8"
        >
          <Link
            href="/"
            className="inline-flex items-center gap-2 text-[16px] font-semibold tracking-tight text-ink transition-opacity hover:opacity-70"
          >
            <LogoMark className="h-[1.15em] w-[1.15em] text-accent" />
            <span className="whitespace-nowrap">
              OR<span className="text-accent">ION</span>
            </span>
          </Link>
          <div className="flex items-center gap-4">
            <ThemeToggle />
            <Link
              href="/negotiate"
              className="rounded bg-accent px-4 py-2 text-[13px] font-medium text-accent-ink transition-colors hover:bg-accent-hover"
            >
              Start
            </Link>
          </div>
        </nav>
      </header>

      <main className="mx-auto max-w-3xl px-5 py-14 sm:px-8">{children}</main>

      <footer className="mx-auto max-w-3xl px-5 pb-14 sm:px-8">
        <div className="flex flex-col gap-3 border-t border-line pt-8 text-[12px] text-muted sm:flex-row sm:items-center sm:justify-between">
          <Link href="/" className="transition-colors hover:text-ink">
            &larr; Back to Orion
          </Link>
          <span className="font-mono text-[10px] uppercase tracking-[0.18em]">
            Voice by AssemblyAI
          </span>
        </div>
      </footer>
    </div>
  );
}
