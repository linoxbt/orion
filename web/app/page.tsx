import Link from "next/link";
import { SiteHeader } from "@/components/site-header";
import { FadeIn } from "@/components/fade-in";

// The numbers a visitor is really asking about, in the place they ask.
// Sourced from the build spec's market analysis (Section 2), which cites
// industry studies on human bill-negotiation services rather than Orion's own
// results - Orion has not run at volume yet, and inventing a win rate would be
// the one thing that breaks trust on a page like this.
const PROOF = [
  { figure: "$10-50", unit: "per month", label: "typical saving on a recurring bill" },
  { figure: "0", unit: "up front", label: "you pay only a share of what is saved" },
  { figure: "4 min", unit: "average", label: "a call you never have to sit through" },
];

const STEPS = [
  {
    n: "01",
    title: "Send us the bill",
    body: "Photo or PDF. Your rate and plan are read off it. Nothing to type.",
  },
  {
    n: "02",
    title: "Orion makes the call",
    body: "It asks for retention, argues your case, and refuses the first offer.",
  },
  {
    n: "03",
    title: "You approve the outcome",
    body: "The new rate is read back off the recording. No saving, no fee.",
  },
];

const VERTICALS = [
  {
    name: "Cable & internet",
    body: "The most scripted retention desks. The most winnable.",
  },
  {
    name: "Mobile & wireless",
    body: "Naming a competitor reaches the desk with real discount authority.",
  },
  {
    name: "Medical billing",
    body: "Hardship programmes move a bill far more than any monthly plan.",
  },
];

export default function HomePage() {
  return (
    <div className="min-h-screen">
      <SiteHeader />

      <main className="mx-auto max-w-6xl px-6 md:px-10">
        {/* Hero */}
        <section className="grid gap-16 border-b border-line py-20 md:grid-cols-[1.15fr,0.85fr] md:items-end md:py-28">
          <FadeIn>
            <p className="mb-6 font-mono text-[10px] uppercase tracking-[0.22em] text-muted">
              An AI agent that negotiates your bills
            </p>
            <h1 className="font-display text-display-md leading-[1.04] md:text-display-lg">
              Stop overpaying
              <br />
              for the same service.
            </h1>
            <p className="mt-8 max-w-prose text-[16px] leading-[1.65] text-ink-soft">
              Orion calls your provider and negotiates the rate down. Cable, mobile, medical.
              You pay a share of what it saves, and nothing if it saves nothing.
            </p>
            <div className="mt-10 flex flex-wrap items-center gap-x-8 gap-y-4">
              <Link
                href="/negotiate"
                className="rounded bg-accent px-6 py-3 text-[14px] font-medium text-accent-ink shadow-sm transition-colors hover:bg-accent-hover"
              >
                Start a negotiation
              </Link>
              <Link
                href="#how-it-works"
                className="text-[14px] text-ink-soft underline decoration-line-strong underline-offset-[6px] transition-colors hover:text-ink hover:decoration-accent"
              >
                See how it works
              </Link>
            </div>
          </FadeIn>

          <FadeIn delay={0.12}>
            <dl className="grid gap-px overflow-hidden rounded-lg border border-line bg-line">
              {PROOF.map((item) => (
                <div key={item.label} className="bg-surface px-7 py-6">
                  <dt className="flex items-baseline gap-2">
                    <span className="tabular font-display text-[2.4375rem] leading-none text-ink">
                      {item.figure}
                    </span>
                    <span className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted">
                      {item.unit}
                    </span>
                  </dt>
                  <dd className="mt-2 text-[13px] leading-relaxed text-ink-soft">{item.label}</dd>
                </div>
              ))}
            </dl>
            <p className="mt-4 text-[11px] leading-relaxed text-muted">
              Savings ranges are drawn from published studies of human bill-negotiation
              services, not from Orion&rsquo;s own results.
            </p>
          </FadeIn>
        </section>

        {/* How it works */}
        <section id="how-it-works" className="border-b border-line py-20 md:py-24">
          <FadeIn>
            <div className="grid gap-12 md:grid-cols-[0.8fr,1.2fr]">
              <div>
                <p className="mb-5 font-mono text-[10px] uppercase tracking-[0.22em] text-muted">
                  How it works
                </p>
                <h2 className="font-display text-display-sm leading-tight md:text-[2.4375rem]">
                  Three steps, and only one of them is yours.
                </h2>
              </div>
              <ol className="grid gap-0">
                {STEPS.map((step, index) => (
                  <li
                    key={step.n}
                    className={`grid grid-cols-[3rem,1fr] gap-6 py-8 ${
                      index === 0 ? "" : "border-t border-line"
                    }`}
                  >
                    <span className="tabular font-mono text-[11px] tracking-[0.1em] text-accent">
                      {step.n}
                    </span>
                    <div>
                      <h3 className="font-display text-[1.4375rem] leading-snug text-ink">
                        {step.title}
                      </h3>
                      <p className="mt-3 max-w-prose text-[14px] leading-[1.65] text-ink-soft">
                        {step.body}
                      </p>
                    </div>
                  </li>
                ))}
              </ol>
            </div>
          </FadeIn>
        </section>

        {/* Verticals */}
        <section id="verticals" className="border-b border-line py-20 md:py-24">
          <FadeIn>
            <p className="mb-5 font-mono text-[10px] uppercase tracking-[0.22em] text-muted">
              What Orion negotiates
            </p>
            <h2 className="max-w-2xl font-display text-display-sm leading-tight md:text-[2.4375rem]">
              Starting with the bills that are easiest to win.
            </h2>
            <div className="mt-14 grid gap-px overflow-hidden rounded-lg border border-line bg-line md:grid-cols-3">
              {VERTICALS.map((vertical) => (
                <article key={vertical.name} className="bg-surface px-8 py-9">
                  <h3 className="font-display text-[1.5375rem] leading-snug text-ink">
                    {vertical.name}
                  </h3>
                  <p className="mt-4 text-[14px] leading-[1.65] text-ink-soft">{vertical.body}</p>
                </article>
              ))}
            </div>
          </FadeIn>
        </section>

        {/* Trust */}
        <section className="border-b border-line py-20 md:py-24">
          <FadeIn>
            <div className="grid gap-12 md:grid-cols-[0.8fr,1.2fr]">
              <div>
                <p className="mb-5 font-mono text-[10px] uppercase tracking-[0.22em] text-muted">
                  How it behaves
                </p>
                <h2 className="font-display text-display-sm leading-tight md:text-[2.4375rem]">
                  It says what it is.
                </h2>
              </div>
              <div className="max-w-prose space-y-6 text-[15px] leading-[1.7] text-ink-soft">
                <p>It says it is an AI, on every call. It never claims to be you.</p>
                <p>It calls only once you have authorised that specific bill.</p>
                <p>Asked something it cannot verify, it hands the call back rather than guessing.</p>
              </div>
            </div>
          </FadeIn>
        </section>

        <footer className="flex flex-col gap-4 py-12 text-[12px] text-muted sm:flex-row sm:items-center sm:justify-between">
          <span>© {new Date().getFullYear()} Orion</span>
          <span className="font-mono text-[10px] uppercase tracking-[0.18em]">
            Voice by AssemblyAI
          </span>
        </footer>
      </main>
    </div>
  );
}
