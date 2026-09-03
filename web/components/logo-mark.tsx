/**
 * The Orion mark: three diamonds in tight triangular formation, evoking Orion's belt as a
 * single bold geometric primitive, repeated three times. Monochrome by design (one flat fill),
 * the way OKX and Binance's marks read as a single confident shape rather than an illustration.
 */
export function LogoMark({ className = "" }: { className?: string }) {
  return (
    <svg viewBox="13 9 74 74" className={className} role="img" aria-label="Orion">
      <polygon points="50,10 68,28 50,46 32,28" fill="currentColor" />
      <polygon points="68.6,46 86.6,64 68.6,82 50.6,64" fill="currentColor" />
      <polygon points="31.4,46 49.4,64 31.4,82 13.4,64" fill="currentColor" />
    </svg>
  );
}
