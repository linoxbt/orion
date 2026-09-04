/** A continuous horizontal scroll, as on stacks.co's logo band.
 *
 * The list is rendered twice and the track translated by exactly -50%, so the
 * second copy lands where the first began and the loop has no seam. Marked
 * aria-hidden after the first copy, so a screen reader hears the names once
 * rather than twice, and the animation is dropped entirely under
 * prefers-reduced-motion (see globals.css) - a permanent sideways crawl is a
 * real problem for some vestibular conditions.
 */
export function Marquee({ items }: { items: string[] }) {
  return (
    <div className="marquee relative">
      <div className="marquee-track flex w-max gap-14 pr-14">
        {[0, 1].map((copy) => (
          <div
            key={copy}
            aria-hidden={copy === 1}
            className="flex shrink-0 gap-14 pr-14"
          >
            {items.map((name) => (
              <span
                key={`${copy}-${name}`}
                className="whitespace-nowrap text-[20px] font-medium tracking-tight text-[var(--l-muted)] sm:text-[26px]"
              >
                {name}
              </span>
            ))}
          </div>
        ))}
      </div>
    </div>
  );
}
