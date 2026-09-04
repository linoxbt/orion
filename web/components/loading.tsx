import { LogoMark } from "@/components/logo-mark";

/**
 * The product's own loading state, borrowed from the splash on the landing
 * page: the mark, breathing, rather than the word "Loading" in grey.
 *
 * `label` is still rendered for screen readers, and shown in print, because a
 * turning logo communicates nothing to somebody who cannot see it.
 */
export function Loading({
  label = "Loading",
  className = "",
}: {
  label?: string;
  className?: string;
}) {
  return (
    <div
      role="status"
      aria-live="polite"
      className={`flex flex-col items-center justify-center gap-4 py-14 ${className}`}
    >
      <LogoMark className="loading-mark h-9 w-9 text-accent" />
      <p className="font-mono text-[10px] uppercase tracking-[0.22em] text-muted">{label}</p>
    </div>
  );
}
