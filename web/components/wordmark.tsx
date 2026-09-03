import { LogoMark } from "./logo-mark";

/** The Orion wordmark.
 *
 * "ORION" is deliberately a single flex item. When the mark and the letters
 * were siblings under `inline-flex`, "OR" and "ION" became two separate items
 * with the container's gap between them - so it rendered as "OR ION" and, in a
 * narrow sidebar, wrapped onto two lines. The nested span keeps it one word,
 * and `whitespace-nowrap` keeps it on one line at any width.
 */
export function Wordmark({ className = "" }: { className?: string }) {
  return (
    <span className={`inline-flex items-center gap-2 font-semibold tracking-tight ${className}`}>
      <LogoMark className="h-[1.15em] w-[1.15em] text-accent" />
      <span className="whitespace-nowrap">
        OR<span className="text-accent">ION</span>
      </span>
    </span>
  );
}
