import Link from "next/link";
import { LogoMark } from "@/components/logo-mark";
import { LandingNav } from "@/components/landing/landing-nav";
import { Marquee } from "@/components/landing/marquee";
import { SplashIntro } from "@/components/landing/splash-intro";
import { HeroWatermark } from "@/components/landing/hero-watermark";
import { Reveal } from "@/components/landing/reveal";

/** The landing page, in the visual language of stacks.co.
 *
 * Dark warm-neutral ground, a single orange accent, mono eyebrows over large
 * grotesque headlines, and full-bleed bands separated by hairlines. The
 * palette is not a guess: it is lifted from stacks.co's own stylesheet
 * (#131416 ground, #f4f3f0 text, #fc6432 accent, #818688 muted), and
 * Instrument Sans is one of the families they actually ship.
 *
 * It scopes its own tokens rather than using the app's, because the signed-in
 * product is a light editorial surface and this is a dark marketing one. The
 * `.landing` class carries the whole palette, so nothing here leaks into the
 * app shell or fights the theme toggle.
 *
 * Nothing on this page is invented. There are no customer logos, no testimonials
 * and no win rate, because Orion has not run at volume and a fabricated number
 * on a page about saving people money would be the worst possible lie.
 */

const STEPS = [
  { n: "01", title: "Send the bill", body: "Photo or PDF. Your rate and plan are read off it." },
  { n: "02", title: "Orion calls", body: "It asks for retention and refuses the first offer." },
  { n: "03", title: "You keep the difference", body: "The new rate is read back off the recording." },
];

const VERTICALS = [
  {
    tag: "Cable & internet",
    title: "The most scripted desks",
    body: "Retention has discounts the first agent cannot see. Orion asks for them by name.",
  },
  {
    tag: "Mobile & wireless",
    title: "Plan fit, not threats",
    body: "Unused data, a legacy plan, multi-line pricing you already qualify for.",
  },
  {
    tag: "Medical billing",
    title: "Itemise, then reduce",
    body: "Hardship programmes and cash-pay rates move a bill far more than any monthly plan.",
  },
];

const BEHAVIOUR = [
  { label: "Says what it is", body: "It opens every call as an AI representative. It never claims to be you." },
  { label: "Authorised per bill", body: "One consent, one company, one account. Never blanket." },
  { label: "Verified from the recording", body: "The outcome is read back off the call, not self-reported." },
  { label: "Hands back", body: "Asked something it cannot verify, it stops rather than guessing." },
];

const PATHS = [
  {
    name: "Cable & internet",
    steps: [
      "Upload the bill so Orion knows your rate and contract end date",
      "Authorise the call for that account",
      "Rehearse it in your browser, or have Orion dial retention",
    ],
  },
  {
    name: "Mobile & wireless",
    steps: [
      "Upload the bill and check the plan it read off it",
      "Add what the carrier asks for at verification",
      "Orion argues plan fit rather than threatening to leave",
    ],
  },
  {
    name: "Medical billing",
    steps: [
      "Upload the statement, itemised if you have it",
      "Orion requests itemisation first, then hardship review",
      "Nothing is billed unless the recording proves a reduction",
    ],
  },
];

const PROVIDERS = [
  "Comcast", "Verizon", "AT&T", "Spectrum", "T-Mobile", "Xfinity",
  "Cox", "Optimum", "Movistar", "Vodafone", "Sky", "Virgin Media",
];

function Eyebrow({ children }: { children: React.ReactNode }) {
  return (
    <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-[var(--l-accent)]">
      {children}
    </p>
  );
}

export default function HomePage() {
  return (
    <div className="landing font-grotesk">
      <SplashIntro />

      {/* Announcement bar. A real capability, not a slogan. */}
      <div className="border-b border-[var(--l-line)] bg-[var(--l-surface)]">
        <Link
          href="/negotiate"
          className="mx-auto flex max-w-7xl items-center justify-center gap-2 px-5 py-2.5 text-center text-[12px] text-[var(--l-muted)] transition-colors hover:text-[var(--l-text)]"
        >
          <span className="h-1.5 w-1.5 flex-none rounded-full bg-[var(--l-accent)]" />
          <span>Rehearse a negotiation in your browser. No phone line needed.</span>
          <span aria-hidden className="text-[var(--l-accent)]">&rarr;</span>
        </Link>
      </div>

      <LandingNav />

      <main>
        {/* Hero */}
        <section className="relative isolate border-b border-[var(--l-line)]">
          <HeroWatermark />
          <div className="relative z-10 mx-auto grid max-w-7xl gap-14 px-5 py-20 sm:px-8 lg:grid-cols-[1.05fr,0.95fr] lg:items-center lg:gap-16 lg:py-28">
            <div className="animate-reveal">
              <Eyebrow>AI bill negotiation</Eyebrow>
              <h1 className="mt-6 text-[2.6rem] font-medium leading-[1.03] tracking-[-0.03em] text-[var(--l-text)] sm:text-[3.6rem] lg:text-[4.4rem]">
                Stop overpaying
                <br />
                for the same service.
              </h1>
              <p className="mt-7 max-w-lg text-[16px] leading-[1.6] text-[var(--l-muted)] sm:text-[17px]">
                Orion calls your provider and negotiates the rate down. Cable, mobile, medical.
                Five bills a month free. 50 cents a month for as many as you like.
              </p>

              <div className="mt-9 flex flex-col gap-3 sm:flex-row sm:items-center">
                <Link
                  href="/negotiate"
                  className="inline-flex items-center justify-center rounded-full bg-[var(--l-accent)] px-7 py-3.5 text-[14px] font-medium text-[#131416] transition-colors hover:bg-[var(--l-accent-hover)]"
                >
                  Start a negotiation
                </Link>
                <Link
                  href="/docs"
                  className="inline-flex items-center justify-center rounded-full border border-[var(--l-line-strong)] px-7 py-3.5 text-[14px] font-medium text-[var(--l-text)] transition-colors hover:border-[var(--l-text)]"
                >
                  How it works
                </Link>
              </div>
            </div>

            {/* A transcript, because that is what the product actually produces. */}
            <div
              className="animate-reveal rounded-2xl border border-[var(--l-line)] bg-[var(--l-surface)]/90 p-6 backdrop-blur-sm sm:p-8"
              style={{ animationDelay: "220ms", animationFillMode: "backwards" }}
            >
              <div className="flex items-center justify-between border-b border-[var(--l-line)] pb-4">
                <span className="font-mono text-[10px] uppercase tracking-[0.2em] text-[var(--l-muted)]">
                  Live transcript
                </span>
                <span className="flex items-center gap-2 font-mono text-[10px] uppercase tracking-[0.2em] text-[var(--l-accent)]">
                  <span className="live-dot h-1.5 w-1.5 rounded-full bg-[var(--l-accent)]" />
                  On call
                </span>
              </div>
              <div className="mt-5 flex flex-col gap-5 text-[14px] leading-[1.55]">
                {[
                  ["Orion", "I'm an AI assistant calling on behalf of the account holder. Could I reach retention, please?"],
                  ["Agent", "I can offer $79.99 a month for twelve months."],
                  ["Orion", "The promotional rate for this speed tier is $54.99. I'd like that matched without extending the term."],
                  ["Agent", "I can do $54.99 for twelve months."],
                ].map(([who, line], i) => (
                  <div key={i} className="flex gap-3">
                    <span
                      className={`w-14 flex-none font-mono text-[10px] uppercase tracking-[0.16em] ${
                        who === "Orion" ? "text-[var(--l-accent)]" : "text-[var(--l-muted)]"
                      }`}
                    >
                      {who}
                    </span>
                    <span className={who === "Orion" ? "text-[var(--l-text)]" : "text-[var(--l-muted)]"}>
                      {line}
                    </span>
                  </div>
                ))}
              </div>
              <div className="mt-6 flex items-baseline gap-3 border-t border-[var(--l-line)] pt-5">
                <span className="font-mono text-[10px] uppercase tracking-[0.2em] text-[var(--l-muted)]">
                  Saved
                </span>
                <span className="text-[22px] font-medium tracking-tight text-[var(--l-accent)]">
                  $25.00<span className="text-[14px] text-[var(--l-muted)]">/mo</span>
                </span>
              </div>
              <p className="mt-4 font-mono text-[10px] uppercase tracking-[0.16em] text-[var(--l-muted)]">
                Illustration of a call, not a customer record
              </p>
            </div>
          </div>
        </section>

        {/* Marquee. Bills it negotiates, not partners - it claims nothing. */}
        <section className="overflow-hidden border-b border-[var(--l-line)] py-9">
          <p className="mx-auto mb-7 max-w-7xl px-5 font-mono text-[10px] uppercase tracking-[0.2em] text-[var(--l-muted)] sm:px-8">
            Bills Orion negotiates
          </p>
          <Marquee items={PROVIDERS} />
        </section>

        {/* Three steps */}
        <section id="how-it-works" className="depth-blur border-b border-[var(--l-line)]">
          <div className="mx-auto max-w-7xl px-5 py-20 sm:px-8 lg:py-24">
            <Reveal>
              <Eyebrow>How it works</Eyebrow>
              <h2 className="mt-5 max-w-2xl text-[2rem] font-medium leading-[1.1] tracking-[-0.025em] text-[var(--l-text)] sm:text-[2.6rem]">
                Three steps, and you sit none of them out.
              </h2>
            </Reveal>
            <div className="mt-14 grid gap-px overflow-hidden rounded-2xl border border-[var(--l-line)] bg-[var(--l-line)] sm:grid-cols-3">
              {STEPS.map((s) => (
                <div key={s.n} className="bg-[var(--l-surface)] p-7 sm:p-8">
                  <span className="font-mono text-[11px] tracking-[0.16em] text-[var(--l-accent)]">
                    {s.n}
                  </span>
                  <h3 className="mt-6 text-[20px] font-medium tracking-tight text-[var(--l-text)]">
                    {s.title}
                  </h3>
                  <p className="mt-2.5 text-[14px] leading-[1.6] text-[var(--l-muted)]">{s.body}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* Verticals */}
        <section id="verticals" className="border-b border-[var(--l-line)]">
          <div className="mx-auto max-w-7xl px-5 py-20 sm:px-8 lg:py-24">
            <Reveal>
              <Eyebrow>What it negotiates</Eyebrow>
              <h2 className="mt-5 max-w-2xl text-[2rem] font-medium leading-[1.1] tracking-[-0.025em] text-[var(--l-text)] sm:text-[2.6rem]">
                Three bills, three different arguments.
              </h2>
            </Reveal>
            <div className="mt-14 grid gap-10 sm:grid-cols-2 lg:grid-cols-3 lg:gap-12">
              {VERTICALS.map((v) => (
                <div key={v.tag} className="border-t border-[var(--l-line-strong)] pt-7">
                  <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-[var(--l-muted)]">
                    {v.tag}
                  </p>
                  <h3 className="mt-5 text-[22px] font-medium leading-tight tracking-tight text-[var(--l-text)]">
                    {v.title}
                  </h3>
                  <p className="mt-3 text-[14px] leading-[1.65] text-[var(--l-muted)]">{v.body}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* Behaviour */}
        <section className="border-b border-[var(--l-line)]">
          <div className="mx-auto grid max-w-7xl gap-12 px-5 py-20 sm:px-8 lg:grid-cols-[0.8fr,1.2fr] lg:py-24">
            <div>
              <Reveal>
                <Eyebrow>How it behaves</Eyebrow>
                <h2 className="mt-5 text-[2rem] font-medium leading-[1.1] tracking-[-0.025em] text-[var(--l-text)] sm:text-[2.6rem]">
                  It says what it is.
                </h2>
              </Reveal>
            </div>
            <div className="grid gap-px overflow-hidden rounded-2xl border border-[var(--l-line)] bg-[var(--l-line)] sm:grid-cols-2">
              {BEHAVIOUR.map((b) => (
                <div key={b.label} className="bg-[var(--l-surface)] p-7">
                  <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-[var(--l-accent)]">
                    {b.label}
                  </p>
                  <p className="mt-4 text-[14px] leading-[1.6] text-[var(--l-text)]">{b.body}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* Paths - native details/summary, so it works without JavaScript. */}
        <section className="border-b border-[var(--l-line)]">
          <div className="mx-auto max-w-7xl px-5 py-20 sm:px-8 lg:py-24">
            <Reveal>
              <Eyebrow>Where to start</Eyebrow>
              <h2 className="mt-5 max-w-2xl text-[2rem] font-medium leading-[1.1] tracking-[-0.025em] text-[var(--l-text)] sm:text-[2.6rem]">
                Choose your bill.
              </h2>
            </Reveal>
            <div className="mt-12 border-t border-[var(--l-line)]">
              {PATHS.map((p) => (
                <details key={p.name} className="group border-b border-[var(--l-line)]">
                  <summary className="flex cursor-pointer list-none items-center justify-between gap-6 py-7 text-[20px] font-medium tracking-tight text-[var(--l-text)] transition-colors hover:text-[var(--l-accent)] sm:text-[24px]">
                    {p.name}
                    <span
                      aria-hidden
                      className="flex-none text-[22px] text-[var(--l-muted)] transition-transform duration-300 group-open:rotate-45"
                    >
                      +
                    </span>
                  </summary>
                  <ol className="grid gap-5 pb-9 sm:grid-cols-3 sm:gap-8">
                    {p.steps.map((step, i) => (
                      <li key={i} className="border-t border-[var(--l-line-strong)] pt-4">
                        <span className="font-mono text-[10px] tracking-[0.16em] text-[var(--l-accent)]">
                          0{i + 1}
                        </span>
                        <p className="mt-3 text-[14px] leading-[1.6] text-[var(--l-muted)]">{step}</p>
                      </li>
                    ))}
                  </ol>
                </details>
              ))}
            </div>
          </div>
        </section>

        {/* Close */}
        <section className="border-b border-[var(--l-line)]">
          <div className="mx-auto max-w-7xl px-5 py-24 text-center sm:px-8 lg:py-32">
            <h2 className="mx-auto max-w-3xl text-[2.2rem] font-medium leading-[1.05] tracking-[-0.03em] text-[var(--l-text)] sm:text-[3.4rem]">
              Your bill went up quietly.
              <br />
              <span className="text-[var(--l-accent)]">Push it back down.</span>
            </h2>
            <Link
              href="/negotiate"
              className="mt-11 inline-flex items-center justify-center rounded-full bg-[var(--l-accent)] px-8 py-4 text-[15px] font-medium text-[#131416] transition-colors hover:bg-[var(--l-accent-hover)]"
            >
              Start a negotiation
            </Link>
          </div>
        </section>
      </main>

      <footer className="mx-auto max-w-7xl px-5 py-16 sm:px-8">
        <div className="grid gap-12 sm:grid-cols-2 lg:grid-cols-4">
          <div>
            <span className="inline-flex items-center gap-2 text-[17px] font-semibold tracking-tight text-[var(--l-text)]">
              <LogoMark className="h-[1.15em] w-[1.15em] text-[var(--l-accent)]" />
              <span className="whitespace-nowrap">
                OR<span className="text-[var(--l-accent)]">ION</span>
              </span>
            </span>
            <p className="mt-4 max-w-xs text-[13px] leading-[1.6] text-[var(--l-muted)]">
              An AI agent that calls your providers and negotiates your bills down.
            </p>
          </div>

          {[
            { head: "Product", links: [["Start a negotiation", "/negotiate"], ["Dashboard", "/dashboard"], ["Playbooks", "/playbooks"], ["Billing", "/billing"]] },
            { head: "Learn", links: [["How it works", "/docs"], ["Authorisation", "/authorization"], ["Account", "/account"]] },
            { head: "Account", links: [["Sign in", "/login"], ["Settings", "/settings"]] },
          ].map((col) => (
            <div key={col.head}>
              <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-[var(--l-muted)]">
                {col.head}
              </p>
              <ul className="mt-5 flex flex-col gap-3">
                {col.links.map(([label, href]) => (
                  <li key={href}>
                    <Link
                      href={href}
                      className="text-[14px] text-[var(--l-text)] transition-colors hover:text-[var(--l-accent)]"
                    >
                      {label}
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>

        <div className="mt-16 flex flex-col gap-3 border-t border-[var(--l-line)] pt-8 text-[12px] text-[var(--l-muted)] sm:flex-row sm:items-center sm:justify-between">
          <span>&copy; {new Date().getFullYear()} Orion</span>
          <span className="font-mono text-[10px] uppercase tracking-[0.18em]">
            Voice by AssemblyAI
          </span>
        </div>
      </footer>
    </div>
  );
}
