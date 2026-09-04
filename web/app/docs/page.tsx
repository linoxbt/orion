import Link from "next/link";
import { DocsFooterNav } from "@/components/docs/docs-footer-nav";
import { Lede, Note } from "@/components/docs/prose";
import { DOCS, docPath } from "@/lib/docs-nav";
import { appHref } from "@/lib/site-urls";

export const metadata = {
  title: "Orion documentation",
  description:
    "What Orion says on your behalf, what it needs from you first, and where it stops.",
};

export default function DocsIndex() {
  return (
    <article>
      <p className="font-mono text-[10px] uppercase tracking-[0.22em] text-muted">Documentation</p>
      <h1 className="mt-4 text-[2.4rem] font-medium leading-[1.05] tracking-[-0.025em] text-ink">
        How Orion works
      </h1>
      <Lede>
        Orion reads your bill, telephones your provider, and negotiates the rate down using the
        retention levers a professional would use. This is what it says on your behalf, what it
        needs from you first, and where it stops.
      </Lede>

      <Note>
        New here? <Link href={docPath("how-a-negotiation-works")} className="text-accent underline decoration-transparent underline-offset-4 transition hover:decoration-current">How a negotiation works</Link>{" "}
        walks the whole thing end to end in six steps.
      </Note>

      {DOCS.map((section) => (
        <section key={section.title} className="mt-12">
          <h2 className="font-mono text-[10px] uppercase tracking-[0.22em] text-muted">
            {section.title}
          </h2>
          <div className="mt-4 grid gap-3 sm:grid-cols-2">
            {section.pages
              .filter((page) => page.slug)
              .map((page) => (
                <Link
                  key={page.slug}
                  href={docPath(page.slug)}
                  className="group rounded border border-line bg-surface p-5 transition-colors hover:border-accent"
                >
                  <span className="block text-[15px] font-medium text-ink group-hover:text-accent">
                    {page.title}
                  </span>
                  <span className="mt-2 block text-[13.5px] leading-[1.6] text-ink-soft">
                    {page.summary}
                  </span>
                </Link>
              ))}
          </div>
        </section>
      ))}

      <section className="mt-14 rounded border border-line bg-surface-2 p-7">
        <p className="text-[15px] font-medium text-ink">Ready to try it?</p>
        <p className="mt-2 text-[14px] leading-relaxed text-ink-soft">
          Rehearsal mode runs the full agent over your microphone, with no phone line and no cost.
        </p>
        <Link
          href={appHref("/negotiate")}
          className="mt-5 inline-flex rounded bg-accent px-5 py-2.5 text-[14px] font-medium text-accent-ink transition-colors hover:bg-accent-hover"
        >
          Start a negotiation
        </Link>
      </section>

      <DocsFooterNav slug="" />
    </article>
  );
}
