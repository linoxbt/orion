/** The shared furniture of a documentation page. */

export function Lede({ children }: { children: React.ReactNode }) {
  return <p className="mt-5 text-[17px] leading-[1.65] text-ink-soft">{children}</p>;
}

export function P({ children }: { children: React.ReactNode }) {
  return <p className="mt-5 text-[15px] leading-[1.75] text-ink-soft">{children}</p>;
}

export function H2({ children }: { children: React.ReactNode }) {
  return (
    <h2 className="mt-12 text-[1.5rem] font-medium leading-snug tracking-tight text-ink">
      {children}
    </h2>
  );
}

/** A numbered beat in a genuine sequence - never used for a plain list. */
export function Step({
  n,
  title,
  children,
}: {
  n: number;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex gap-4 border-b border-line py-5 last:border-b-0">
      <span className="mt-0.5 flex h-6 w-6 flex-none items-center justify-center rounded-full border border-line bg-surface-2 font-mono text-[10px] text-accent">
        {n}
      </span>
      <div>
        <p className="text-[15px] font-medium text-ink">{title}</p>
        <p className="mt-1.5 text-[14px] leading-[1.65] text-ink-soft">{children}</p>
      </div>
    </div>
  );
}

export function Card({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="rounded border border-line bg-surface p-5">
      <p className="text-[15px] font-medium text-ink">{title}</p>
      <p className="mt-2 text-[14px] leading-[1.65] text-ink-soft">{children}</p>
    </div>
  );
}

/** Something the reader should not miss. */
export function Note({ children }: { children: React.ReactNode }) {
  return (
    <div className="mt-6 rounded border-l-2 border-accent bg-accent-soft px-5 py-4">
      <p className="text-[14px] leading-[1.65] text-ink">{children}</p>
    </div>
  );
}
