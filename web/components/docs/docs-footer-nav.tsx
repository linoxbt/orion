import Link from "next/link";
import { ArrowLeft, ArrowRight } from "lucide-react";
import { docPath, neighbours } from "@/lib/docs-nav";

/** Where to go next, at the foot of every page.
 *
 * Documentation is read in order more often than it is searched, and a page
 * that ends with nothing is a dead end. */
export function DocsFooterNav({ slug }: { slug: string }) {
  const { prev, next } = neighbours(slug);
  if (!prev && !next) return null;

  return (
    <nav
      aria-label="More documentation"
      className="mt-16 grid gap-4 border-t border-line pt-8 sm:grid-cols-2"
    >
      {prev ? (
        <Link
          href={docPath(prev.slug)}
          className="group rounded border border-line p-5 transition-colors hover:border-accent"
        >
          <span className="flex items-center gap-2 font-mono text-[10px] uppercase tracking-[0.2em] text-muted">
            <ArrowLeft size={12} /> Previous
          </span>
          <span className="mt-2 block text-[15px] text-ink group-hover:text-accent">
            {prev.title}
          </span>
        </Link>
      ) : (
        <span />
      )}

      {next && (
        <Link
          href={docPath(next.slug)}
          className="group rounded border border-line p-5 text-right transition-colors hover:border-accent sm:col-start-2"
        >
          <span className="flex items-center justify-end gap-2 font-mono text-[10px] uppercase tracking-[0.2em] text-muted">
            Next <ArrowRight size={12} />
          </span>
          <span className="mt-2 block text-[15px] text-ink group-hover:text-accent">
            {next.title}
          </span>
        </Link>
      )}
    </nav>
  );
}
