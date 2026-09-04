import Link from "next/link";

/** What "authorised" means, in plain terms.
 *
 * This page used to describe a DocuSign flow. That flow was removed: because
 * DocuSign was never configured, `authorized` could never become true, the
 * call button never rendered, and no call could ever be placed. Consent is now
 * recorded in the app, and this page describes that rather than a process
 * nobody goes through.
 */
export default function AuthorizationPage() {
  return (
    <div className="max-w-2xl">
      <p className="font-mono text-[10px] uppercase tracking-[0.22em] text-muted">Authorisation</p>
      <h1 className="mt-4 font-display text-[2.4375rem] leading-none text-ink">
        Consent &amp; authorisation
      </h1>
      <p className="mt-4 max-w-prose text-[14px] leading-relaxed text-ink-soft">
        Authorise once per negotiation, on that negotiation&rsquo;s own page. Never blanket.
      </p>

      <ul className="mt-8 flex flex-col gap-4">
        <li className="rounded-lg border border-line bg-surface p-6">
          <p className="font-display text-[1.1875rem] text-ink">What you agree to</p>
          <p className="mt-2 text-[14px] leading-relaxed text-ink-soft">
            Orion may contact this company as your representative, discuss this account, and
            record the call. You confirm the account is yours to authorise.
          </p>
        </li>
        <li className="rounded-lg border border-line bg-surface p-6">
          <p className="font-display text-[1.1875rem] text-ink">What gets recorded</p>
          <p className="mt-2 text-[14px] leading-relaxed text-ink-soft">
            Your name, the exact wording, the moment. A ticked box is not a record.
          </p>
        </li>
        <li className="rounded-lg border border-line bg-surface p-6">
          <p className="font-display text-[1.1875rem] text-ink">On the call itself</p>
          <p className="mt-2 text-[14px] leading-relaxed text-ink-soft">
            It says it is an AI in its opening line, and always gives a recording notice. Asked
            something it cannot verify, it hands the call back.
          </p>
        </li>
      </ul>

      <p className="mt-8 text-[14px] leading-relaxed text-ink-soft">
        {" "}
        <Link
          href="/dashboard"
          className="text-accent underline decoration-transparent underline-offset-4 transition hover:decoration-current"
        >
          Open a negotiation
        </Link>{" "}
        to authorise it.
      </p>
    </div>
  );
}
