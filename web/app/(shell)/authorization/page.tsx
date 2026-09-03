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
        A company won&rsquo;t discuss an account with anyone who isn&rsquo;t entitled to act on it.
        Before Orion places a call, you authorise it once for that specific negotiation - on the
        negotiation&rsquo;s own page, not here.
      </p>

      <ul className="mt-8 flex flex-col gap-4">
        <li className="rounded-lg border border-line bg-surface p-6">
          <p className="font-display text-[1.1875rem] text-ink">What you agree to</p>
          <p className="mt-2 text-[14px] leading-relaxed text-ink-soft">
            That Orion may contact the company as your representative about that account or
            purchase, discuss it on your behalf, and record the call for verification - and that
            you are the account holder or otherwise entitled to authorise it.
          </p>
        </li>
        <li className="rounded-lg border border-line bg-surface p-6">
          <p className="font-display text-[1.1875rem] text-ink">What gets recorded</p>
          <p className="mt-2 text-[14px] leading-relaxed text-ink-soft">
            The name you type, the exact version of the wording you agreed to, and the moment you
            agreed. Stored against that negotiation, so what was authorised can be reconstructed
            later rather than resting on &ldquo;a box was ticked&rdquo;.
          </p>
        </li>
        <li className="rounded-lg border border-line bg-surface p-6">
          <p className="font-display text-[1.1875rem] text-ink">On the call itself</p>
          <p className="mt-2 text-[14px] leading-relaxed text-ink-soft">
            Orion identifies itself as an AI representative in its opening line - it never claims
            to be you - and gives a recording notice regardless of local two-party-consent rules.
            If a representative asks for something it can&rsquo;t verify, it hands the call back to
            you rather than guessing.
          </p>
        </li>
      </ul>

      <p className="mt-8 text-[14px] leading-relaxed text-ink-soft">
        Authorisation is per negotiation, never blanket.{" "}
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
