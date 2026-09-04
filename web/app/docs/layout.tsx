import Link from "next/link";
import { LogoMark } from "@/components/logo-mark";
import { DocsSidebar } from "@/components/docs/docs-sidebar";
import { appHref, siteHref } from "@/lib/site-urls";

/**
 * The documentation, laid out as documentation.
 *
 * A persistent left-hand contents column, a search that focuses on Cmd-K, and
 * a measured reading column beside it. This is public: it is the landing
 * page's main call to action, and asking a stranger to create an account to
 * read what the product does would be absurd.
 */
export default function DocsLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen bg-paper">
      <header className="sticky top-0 z-40 border-b border-line bg-paper/90 backdrop-blur-md">
        <div className="mx-auto flex max-w-7xl items-center justify-between gap-4 px-5 py-4 sm:px-8">
          <div className="flex items-baseline gap-3">
            <Link
              href={siteHref("/")}
              className="inline-flex items-center gap-2 text-[16px] font-semibold tracking-tight text-ink transition-opacity hover:opacity-70"
            >
              <LogoMark className="h-[1.15em] w-[1.15em] text-accent" />
              <span className="whitespace-nowrap">
                OR<span className="text-accent">ION</span>
              </span>
            </Link>
            <span className="font-mono text-[11px] uppercase tracking-[0.2em] text-muted">
              Docs
            </span>
          </div>

          <div className="flex items-center gap-5">
            <Link
              href={siteHref("/")}
              className="hidden text-[13px] text-ink-soft transition-colors hover:text-ink sm:block"
            >
              Home
            </Link>
            <Link
              href={appHref("/negotiate")}
              className="rounded bg-accent px-4 py-2 text-[13px] font-medium text-accent-ink transition-colors hover:bg-accent-hover"
            >
              Start a negotiation
            </Link>
          </div>
        </div>
      </header>

      <div className="mx-auto grid max-w-7xl gap-12 px-5 py-12 sm:px-8 lg:grid-cols-[16rem,minmax(0,1fr)] lg:gap-16">
        <DocsSidebar />
        <main className="min-w-0 max-w-3xl">{children}</main>
      </div>

      <footer className="border-t border-line">
        <div className="mx-auto flex max-w-7xl flex-col gap-3 px-5 py-10 text-[12px] text-muted sm:flex-row sm:items-center sm:justify-between sm:px-8">
          <span>&copy; {new Date().getFullYear()} Orion</span>
          <span className="font-mono text-[10px] uppercase tracking-[0.18em]">
            Voice by AssemblyAI
          </span>
        </div>
      </footer>
    </div>
  );
}
