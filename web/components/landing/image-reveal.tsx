"use client";

import Image from "next/image";
import { useInView } from "@/lib/use-in-view";

/**
 * A large photograph that settles from blur into focus as you reach it, with
 * a short line of type beside it.
 *
 * The side alternates so a run of these does not read as a template. The
 * image is rendered visible and then animated rather than parked at opacity 0
 * waiting on an observer: if the observer never fires the picture is still
 * there, because the animation is the enhancement, not the thing that makes
 * the page exist.
 */
export function ImageReveal({
  eyebrow,
  title,
  body,
  src,
  side = "right",
}: {
  eyebrow: string;
  title: React.ReactNode;
  body: string;
  src: string;
  side?: "left" | "right";
}) {
  const { ref, inView } = useInView<HTMLDivElement>(0.15);

  return (
    <section className="border-b border-[var(--l-line)]">
      <div
        ref={ref}
        className={`mx-auto grid max-w-7xl items-center gap-12 px-5 py-20 sm:px-8 lg:gap-20 lg:py-28 ${
          side === "right" ? "lg:grid-cols-[0.9fr,1.1fr]" : "lg:grid-cols-[1.1fr,0.9fr]"
        }`}
      >
        <div className={`${inView ? "animate-reveal" : ""} ${side === "right" ? "" : "lg:order-2"}`}>
          <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-[var(--l-accent)]">
            {eyebrow}
          </p>
          <h2 className="mt-5 text-[2.1rem] font-medium leading-[1.05] tracking-[-0.03em] text-[var(--l-text)] sm:text-[3rem]">
            {title}
          </h2>
          <p className="mt-6 max-w-md text-[15px] leading-[1.65] text-[var(--l-muted)] sm:text-[16px]">
            {body}
          </p>
        </div>

        <div
          className={`${inView ? "animate-reveal" : ""} ${side === "right" ? "" : "lg:order-1"}`}
          style={inView ? { animationDelay: "140ms", animationFillMode: "backwards" } : undefined}
        >
          <div className="relative aspect-[4/3] w-full overflow-hidden rounded-2xl border border-[var(--l-line)]">
            <Image
              src={src}
              alt=""
              fill
              sizes="(max-width: 1024px) 100vw, 55vw"
              className="object-cover grayscale contrast-110"
            />
            {/* Tinted so the photograph sits in the page's own register rather
                than reading as a stock image dropped on top of it. */}
            <div className="absolute inset-0 bg-[var(--l-bg)]/25" />
          </div>
        </div>
      </div>
    </section>
  );
}
