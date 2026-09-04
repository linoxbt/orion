import Link from "next/link";
import { PlaybookList } from "@/components/playbook-list";

/** How Orion works, for the person using it.
 *
 * Separate from the README, which is written for whoever runs the code. This
 * page answers the questions the interface itself keeps raising: what the
 * agent will actually say, why a call needs authorising, what "bill type"
 * changes, and why the real-call button is sometimes greyed out.
 */

export const metadata = {
  title: "How Orion works",
  description: "What the agent does on a call, what it needs from you, and what it will never do.",
};

function Label({ children }: { children: React.ReactNode }) {
  return (
    <p className="font-mono text-[9px] uppercase tracking-[0.22em] text-muted">{children}</p>
  );
}

function Section({
  id,
  label,
  title,
  children,
}: {
  id: string;
  label: string;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section id={id} className="scroll-mt-24 border-t border-line pt-10">
      <Label>{label}</Label>
      <h2 className="mt-3 font-display text-[1.6875rem] leading-snug text-ink">{title}</h2>
      <div className="mt-4 flex flex-col gap-4 text-[14px] leading-relaxed text-ink-soft">
        {children}
      </div>
    </section>
  );
}

function Step({ n, title, children }: { n: string; title: string; children: React.ReactNode }) {
  return (
    <div className="flex gap-4">
      <span className="mt-0.5 flex h-6 w-6 flex-none items-center justify-center rounded-full border border-line bg-surface-2 font-mono text-[10px] text-accent">
        {n}
      </span>
      <div>
        <p className="font-display text-[1.1875rem] leading-snug text-ink">{title}</p>
        <p className="mt-1 text-[14px] leading-relaxed text-ink-soft">{children}</p>
      </div>
    </div>
  );
}

const CONTENTS = [
  ["what-it-does", "What Orion actually does"],
  ["the-run", "A negotiation, start to finish"],
  ["bill-type", "What bill type changes"],
  ["two-ways-to-call", "Rehearsal and the real call"],
  ["authorisation", "Why a call needs authorising"],
  ["playbooks", "The playbooks it argues from"],
  ["stalls", "When a call needs you"],
  ["verification", "How a saving gets verified"],
  ["after", "Receipts and renewals"],
  ["limits", "What it will not do"],
];

export default function DocsPage() {
  return (
    <div className="max-w-3xl pb-16">
      <Label>Documentation</Label>
      <h1 className="mt-4 font-display text-[2.4375rem] leading-none text-ink">How Orion works</h1>
      <p className="mt-4 max-w-prose text-[15px] leading-relaxed text-ink-soft">
        Orion reads your bill, calls the company, and negotiates the rate down using the retention
        levers a professional would use. This page covers what it says on your behalf, what it
        needs from you first, and where it stops.
      </p>

      <nav aria-label="Contents" className="mt-8 rounded-lg border border-line bg-surface p-5">
        <Label>On this page</Label>
        <ul className="mt-3 grid gap-2 sm:grid-cols-2">
          {CONTENTS.map(([id, title]) => (
            <li key={id}>
              <a
                href={`#${id}`}
                className="text-[13px] text-accent underline decoration-transparent underline-offset-4 transition hover:decoration-current"
              >
                {title}
              </a>
            </li>
          ))}
        </ul>
      </nav>

      <div className="mt-12 flex flex-col gap-12">
        <Section id="what-it-does" label="Overview" title="What Orion actually does">
          <p>
            Companies price on inertia. The advertised rate for a new customer is routinely lower
            than what an existing one pays, and the gap is recovered only by asking, usually by
            being transferred to a retention desk that has discounts the first agent cannot see.
            Orion is the part of that most people never get round to.
          </p>
          <p>
            It is a voice agent, not a form filler. It holds a real conversation: it waits through
            the hold music, presses the right menu keys, states your case, counters the first offer,
            and stops when the concession is real rather than accepting the first number quoted.
          </p>
        </Section>

        <Section id="the-run" label="Lifecycle" title="A negotiation, start to finish">
          <Step n="1" title="Upload the bill">
            A photo, a PDF, a screenshot, a scan. The provider, your current rate, the plan and the
            contract end date are read straight off it, so there is nothing to type. If a field
            cannot be read it is left blank rather than guessed at.
          </Step>
          <Step n="2" title="Check what was read">
            Extraction is good, not infallible. Everything it found is shown back to you as editable
            fields before anything is dialled, because the agent argues from these numbers and a
            wrong rate makes for a wrong argument.
          </Step>
          <Step n="3" title="Add what proves the account is yours">
            Companies verify before they discuss an account. The last four digits, a PIN, a date of
            birth: whatever that provider asks for. These are encrypted at rest and used only to
            answer a verification question on the call.
          </Step>
          <Step n="4" title="Authorise the call">
            One signed consent for that specific negotiation. See below for what it covers.
          </Step>
          <Step n="5" title="Listen in">
            The transcript streams live as the call happens. You can read the conversation turn by
            turn while it is still going.
          </Step>
          <Step n="6" title="Get the outcome">
            The call recording is transcribed afterwards and the result is read back out of it. A
            saving is only recorded if the recording actually supports it.
          </Step>
        </Section>

        <Section id="bill-type" label="Configuration" title="What bill type changes">
          <p>
            Bill type is not a label. It selects the playbook the agent argues from, and the three
            are genuinely different negotiations.
          </p>
          <ul className="flex flex-col gap-3">
            <li className="rounded border border-line bg-surface p-4">
              <p className="font-display text-[1.1875rem] text-ink">Cable and internet</p>
              <p className="mt-1">
                Ask for retention by name, cite the competitor promotion in your area, treat the
                promotional rate expiry as the lever. The biggest concessions live on this desk.
              </p>
            </li>
            <li className="rounded border border-line bg-surface p-4">
              <p className="font-display text-[1.1875rem] text-ink">Mobile</p>
              <p className="mt-1">
                Argue on plan fit rather than threat: unused data, a legacy plan that has been
                superseded, multi-line pricing you already qualify for but are not on.
              </p>
            </li>
            <li className="rounded border border-line bg-surface p-4">
              <p className="font-display text-[1.1875rem] text-ink">Medical</p>
              <p className="mt-1">
                An itemised bill first, then charity care and financial hardship programmes, then a
                prompt-pay discount. Never a threat to leave, which does nothing here and is the
                wrong register for a hospital billing office.
              </p>
            </li>
          </ul>
          <p>
            Pick the wrong one and the agent will still be polite and still get through
            verification, but it will be pulling levers the person on the other end cannot act on.
          </p>
        </Section>

        <Section id="two-ways-to-call" label="Calling" title="Rehearsal and the real call">
          <p>
            <span className="font-medium text-ink">Rehearsal</span> runs the identical agent over
            your microphone, with you playing the representative. Same playbook, same voice, same
            counters. It costs nothing, dials nobody, and is the honest way to hear what Orion will
            say before it says it to a company.
          </p>
          <p>
            <span className="font-medium text-ink">The real call</span> dials the provider over a
            phone line. It appears greyed out until three things are true: you have authorised it, a
            phone line is connected to this deployment, and the negotiation has not already been
            called. The panel tells you which of the three is missing rather than simply hiding the
            button, which is what it used to do.
          </p>
          <p className="rounded border border-line bg-surface-2 p-4">
            If no phone line is configured, everything else still works. Rehearsal is the full agent,
            not a demo of it.
          </p>
        </Section>

        <Section id="authorisation" label="Consent" title="Why a call needs authorising">
          <p>
            A company will not discuss an account with someone who is not entitled to act on it, and
            recording a call carries obligations in plenty of places. So authorisation is per
            negotiation and never blanket: you are agreeing that Orion may contact this company
            about this account, discuss it on your behalf, and record the call.
          </p>
          <p>
            What is stored is the name you typed, the exact wording you agreed to, and the moment
            you agreed, so what was authorised can be reconstructed later rather than resting on
            the fact that a box was ticked.
          </p>

          <ul className="flex flex-col gap-3">
            {[
              [
                "What you agree to",
                "Orion may contact this company as your representative, discuss this account, and record the call. You confirm the account is yours to authorise.",
              ],
              [
                "What gets recorded",
                "Your name, the exact wording, the moment. A ticked box is not a record.",
              ],
              [
                "On the call itself",
                "It says it is an AI in its opening line, and always gives a recording notice. Asked something it cannot verify, it hands the call back rather than guessing.",
              ],
            ].map(([title, body]) => (
              <li key={title} className="rounded border border-line bg-surface p-5">
                <p className="font-display text-[1.1875rem] text-ink">{title}</p>
                <p className="mt-2 text-[14px] leading-relaxed text-ink-soft">{body}</p>
              </li>
            ))}
          </ul>
        </Section>

        <Section id="playbooks" label="Strategy" title="The playbooks it argues from">
          <p>
            Public retention tactics as a baseline, with a provider-specific playbook where one
            exists. Which desk to ask for and what tends to work, not proprietary offer tiers.
          </p>
          <PlaybookList />
        </Section>

        <Section id="stalls" label="Escalation" title="When a call needs you">
          <p>
            Sometimes a representative asks for something Orion cannot answer: a PIN it was never
            given, a security question with no stored answer, a decision that is genuinely yours to
            make. When that happens it does not guess and it does not quietly give up. It messages
            you while the call is still live, because a customer who finds out tomorrow has already
            lost the call.
          </p>
          <p>
            Where it reaches you is yours to set, on the{" "}
            <Link
              href="/account"
              className="text-accent underline decoration-transparent underline-offset-4 transition hover:decoration-current"
            >
              account page
            </Link>{" "}
            under &ldquo;If a call needs you&rdquo;: a WhatsApp number, an email address, or
            neither. Leave both blank and Orion simply carries on alone, ending the call politely
            rather than pressing on with a guess.
          </p>
        </Section>

        <Section id="verification" label="Trust" title="How a saving gets verified">
          <p>
            An agent that reports its own success is marking its own homework. Orion does not record
            an outcome from what it believes happened on the call. After the call ends, the
            recording is transcribed and the result is read back out of that transcript: the new
            rate, the confirmation number, what was actually agreed.
          </p>
          <p>
            A negotiation that cannot be verified this way stays unverified, is never counted as a
            saving, and is never billed for. That is the whole point of recording.
          </p>
        </Section>

        <Section id="after" label="Afterwards" title="Receipts and renewals">
          <p>
            A verified saving produces a receipt: provider, the rate before and after, and the
            confirmation number. It is shareable by link and deliberately thin. It carries no phone
            number, no account details and no transcript, because a link forwarded to a friend must
            not become a way to read a stranger&rsquo;s account.
          </p>
          <p>
            Negotiated rates expire. Orion reads the contract end date off the bill and surfaces the
            negotiation again about six weeks before the promotional period lapses, which is the
            point at which calling a second time is worth something and the point most people miss.
          </p>
        </Section>

        <Section id="limits" label="Boundaries" title="What it will not do">
          <ul className="flex flex-col gap-2">
            {[
              "Claim to be you. It identifies itself as an AI representative calling on your behalf, in its opening line, every time.",
              "Skip the recording notice, regardless of local consent rules.",
              "Agree to a new contract term, an upgrade, or anything that adds cost, even when offered one that lowers the monthly rate.",
              "Answer a verification question you have not given it the answer to. It hands the call back rather than guessing.",
              "Report a saving the recording does not support.",
            ].map((line) => (
              <li key={line} className="flex gap-3 rounded border border-line bg-surface p-4">
                <span aria-hidden className="mt-1.5 h-1 w-1 flex-none rounded-full bg-fail" />
                <span>{line}</span>
              </li>
            ))}
          </ul>
        </Section>
      </div>

      <p className="mt-12 border-t border-line pt-6 text-[13px] leading-relaxed text-muted">
        Running Orion yourself, or wiring up a phone line, billing or the database? That is in the
        README in the repository, which covers configuration and deployment.
      </p>
    </div>
  );
}
