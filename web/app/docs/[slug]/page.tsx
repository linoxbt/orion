import { notFound } from "next/navigation";
import { PlaybookList } from "@/components/playbook-list";
import { DocsFooterNav } from "@/components/docs/docs-footer-nav";
import { Card, H2, Lede, Note, P, Step } from "@/components/docs/prose";
import { DOC_ORDER, findDoc } from "@/lib/docs-nav";

export function generateStaticParams() {
  return DOC_ORDER.filter((p) => p.slug).map((p) => ({ slug: p.slug }));
}

export async function generateMetadata({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const page = findDoc(slug);
  return page ? { title: `${page.title} — Orion docs`, description: page.summary } : {};
}

const CONTENT: Record<string, React.ReactNode> = {
  "how-a-negotiation-works": (
    <>
      <Lede>
        Six steps. You do the first three, which take a couple of minutes; Orion does the rest.
      </Lede>
      <div className="mt-8">
        <Step n={1} title="Upload the bill">
          A photo, a PDF, a screenshot, a scan. The provider, your current rate, the plan and the
          contract end date are read straight off it. A field that cannot be read is left blank
          rather than guessed at.
        </Step>
        <Step n={2} title="Check what was read">
          Everything found is shown back as editable fields before anything is dialled. The agent
          argues from these numbers, and a wrong rate makes a wrong argument.
        </Step>
        <Step n={3} title="Add what proves the account is yours">
          The last four digits, a PIN, a date of birth, whatever that provider asks for. Encrypted
          at rest and used only to answer a verification question on the call.
        </Step>
        <Step n={4} title="Authorise the call">
          One consent for that specific negotiation. Never blanket.
        </Step>
        <Step n={5} title="Listen in">
          The transcript streams turn by turn while the call is still going.
        </Step>
        <Step n={6} title="Get the outcome">
          The recording is transcribed afterwards and the result read back out of it, along with
          Orion&rsquo;s own view of what you should do next.
        </Step>
      </div>
      <Note>
        Orion will wait on hold. Retention queues run for minutes, and it stays on the line rather
        than giving up, because that queue is where the discounts are.
      </Note>
    </>
  ),

  "bill-types": (
    <>
      <Lede>
        Bill type is not a label. It selects the playbook the agent argues from, and the three are
        genuinely different negotiations.
      </Lede>
      <div className="mt-8 flex flex-col gap-4">
        <Card title="Cable and internet">
          Ask for retention by name, cite the competitor promotion in your area, treat the
          promotional rate expiry as the lever. The biggest concessions live on this desk.
        </Card>
        <Card title="Mobile and wireless">
          Argue on plan fit rather than threat: unused data, a legacy plan that has been
          superseded, multi-line pricing you already qualify for but are not on.
        </Card>
        <Card title="Medical billing">
          An itemised bill first, then charity care and financial hardship programmes, then a
          prompt-pay discount. Never a threat to leave, which does nothing here.
        </Card>
      </div>
      <P>
        Pick the wrong one and the agent will still be polite and still get through verification,
        but it will be pulling levers the person on the other end cannot act on.
      </P>
    </>
  ),

  "rehearsal-and-real-calls": (
    <>
      <Lede>Two ways to run a negotiation, and only one of them dials anybody.</Lede>
      <H2>Rehearsal</H2>
      <P>
        The identical agent, over your microphone, with you playing the representative. Same
        playbook, same voice, same counters, same tools. It costs nothing, dials nobody, and works
        with no phone line configured at all. It is the honest way to hear what Orion will say
        before it says it to a company.
      </P>
      <H2>The real call</H2>
      <P>
        Dials the provider over a phone line. It requires your authorisation, a connected phone
        line, and a negotiation that is not already mid-call. Where one of those is missing the
        panel says which, rather than hiding the button.
      </P>
      <P>
        A negotiation can be called as many times as it takes. The first attempt often reaches
        nobody, and every attempt is kept.
      </P>
    </>
  ),

  playbooks: (
    <>
      <Lede>
        Public retention tactics as a baseline, with a provider-specific playbook where one
        exists. Which desk to ask for and what tends to work, not proprietary offer tiers.
      </Lede>
      <div className="mt-8">
        <PlaybookList />
      </div>
    </>
  ),

  "when-a-call-needs-you": (
    <>
      <Lede>
        Sometimes a representative asks for something Orion cannot answer. It does not guess.
      </Lede>
      <P>
        A PIN it was never given, a security question with no stored answer, a decision that is
        genuinely yours. When that happens it messages you while the call is still live, because a
        customer who finds out tomorrow has already lost the call.
      </P>
      <H2>Setting it up</H2>
      <P>
        Where it reaches you is yours to set on your account page, under &ldquo;If a call needs
        you&rdquo;: a WhatsApp number, an email address, or neither. These are per person, not per
        deployment, so nobody else is told about your negotiation.
      </P>
      <P>
        Leave both blank and Orion carries on alone, ending the call politely rather than pressing
        on with a guess.
      </P>
    </>
  ),

  authorisation: (
    <>
      <Lede>
        A company will not discuss an account with someone not entitled to act on it, and
        recording carries obligations. So you authorise one company, one account, one call.
      </Lede>
      <div className="mt-8 flex flex-col gap-4">
        <Card title="What you agree to">
          Orion may contact this company as your representative, discuss this account, and record
          the call. You confirm the account is yours to authorise.
        </Card>
        <Card title="What gets recorded">
          Your name, the exact wording you agreed to, and the moment you agreed. A ticked box is
          not a record of anything.
        </Card>
        <Card title="On the call itself">
          It says it is an AI in its opening line and always gives a recording notice. Asked
          something it cannot verify, it hands the call back rather than guessing.
        </Card>
      </div>
      <Note>Authorisation is per negotiation. There is no blanket permission to grant.</Note>
    </>
  ),

  verification: (
    <>
      <Lede>An agent that reports its own success is marking its own homework.</Lede>
      <P>
        So Orion does not record an outcome from what it believes happened on the call. After the
        call ends, the recording is transcribed and the result is read back out of that transcript:
        the new rate, the confirmation number, what was actually agreed.
      </P>
      <P>
        A negotiation that cannot be verified this way stays unverified, is never counted as a
        saving, and is never billed for. That is what the recording is for.
      </P>
      <H2>When nothing happened</H2>
      <P>
        If nobody answered, or the call ended before anything was said, no outcome is invented.
        It says the call was not answered, and tells you when to try again.
      </P>
    </>
  ),

  recordings: (
    <>
      <Lede>Every call Orion makes on your behalf is kept, and it is yours.</Lede>
      <P>
        A negotiation is dialled more than once, and every attempt is listed on its page: when it
        ran, whether it was answered, how it ended, how long it lasted, and what came of it. The
        ones that reached nobody are listed too, because a busy line is part of the record.
      </P>
      <P>
        Each recording can be played in the page or downloaded. Links are signed and expire, so a
        copied link stops working rather than becoming a permanent handle on a phone call about
        your account.
      </P>
      <Note>
        Recordings are stored privately and scoped to your account. Nobody else can list or play
        them, including with the negotiation&rsquo;s id.
      </Note>
    </>
  ),

  plans: (
    <>
      <Lede>A bill is the unit. Extraction, the negotiation and every call on it come out of one.</Lede>
      <div className="mt-8 grid gap-4 sm:grid-cols-2">
        <Card title="Free">
          Five bills a month, resetting on the 1st. Everything works: extraction, the full agent,
          rehearsal, live transcripts, recordings and receipts.
        </Card>
        <Card title="Unlimited">
          Fifty cents a month, as many bills as you like. Cancelling stops the next charge and
          keeps the month already paid for.
        </Card>
      </div>
      <P>
        A failed extraction does not cost an allowance. If the model was unavailable, that is our
        problem rather than yours, and the bill is handed back.
      </P>
    </>
  ),

  limits: (
    <>
      <Lede>The lines the agent does not cross, on any call.</Lede>
      <div className="mt-8 flex flex-col gap-3">
        {[
          "Claim to be you. It identifies itself as an AI representative calling on your behalf, in its opening line, every time.",
          "Skip the recording notice, regardless of local consent rules.",
          "Agree to a new contract term, an upgrade, or anything that adds cost, even when offered one that lowers the monthly rate.",
          "Answer a verification question you have not given it the answer to. It hands the call back rather than guessing.",
          "Report a saving the recording does not support.",
        ].map((line) => (
          <div key={line} className="flex gap-3 rounded border border-line bg-surface p-4">
            <span aria-hidden className="mt-[0.55rem] h-1 w-1 flex-none rounded-full bg-fail" />
            <span className="text-[14px] leading-[1.65] text-ink-soft">{line}</span>
          </div>
        ))}
      </div>
    </>
  ),
};

export default async function DocPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const page = findDoc(slug);
  const body = CONTENT[slug];
  if (!page || !body) notFound();

  return (
    <article>
      <p className="font-mono text-[10px] uppercase tracking-[0.22em] text-muted">Documentation</p>
      <h1 className="mt-4 text-[2.2rem] font-medium leading-[1.1] tracking-[-0.02em] text-ink">
        {page.title}
      </h1>
      {body}
      <DocsFooterNav slug={slug} />
    </article>
  );
}
