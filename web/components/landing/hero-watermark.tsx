"use client";

import { useEffect, useState } from "react";
import Image from "next/image";
import { LogoMark } from "@/components/logo-mark";
import { HERO_IMAGES } from "@/lib/landing-images";

const ROTATION_MS = 4400;

/**
 * The large, slowly-turning watermark behind the hero: the Orion mark and the
 * paperwork this product is actually about - statements, invoices, receipts -
 * oversized and cycling one at a time.
 *
 * Each layer crossfades with a distinct scale and rotation coming in and a
 * different one going out, so it reads as one image turning away while the
 * next arrives rather than a flat dissolve. A tint sits between this and the
 * real content, light enough that the imagery still shows through.
 *
 * The rotation stops entirely under prefers-reduced-motion - a permanent
 * cycling background is exactly the kind of ambient motion that causes
 * problems, and a still first frame is a perfectly good page.
 */
export function HeroWatermark() {
  const [active, setActive] = useState(0);
  const total = HERO_IMAGES.length + 1; // + the mark itself

  useEffect(() => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const id = window.setInterval(() => setActive((v) => (v + 1) % total), ROTATION_MS);
    return () => window.clearInterval(id);
  }, [total]);

  return (
    <div className="pointer-events-none absolute inset-0 z-0 overflow-hidden" aria-hidden="true">
      <Layer isActive={active === 0}>
        <LogoMark className="h-[62vw] w-[62vw] max-h-[620px] max-w-[620px] text-[var(--l-accent)] animate-slow-spin" />
      </Layer>

      {HERO_IMAGES.map((img, i) => (
        <Layer key={img.src} isActive={active === i + 1}>
          <div className="relative h-[150vw] w-[150vw] max-h-[1200px] max-w-[1200px] sm:h-[88vw] sm:w-[88vw]">
            <Image
              src={img.src}
              alt={img.alt}
              fill
              sizes="150vw"
              priority={i === 0}
              className="rounded-full object-cover grayscale contrast-125"
            />
          </div>
        </Layer>
      ))}

      {/* Lighter than the page's solid sections, so the imagery reads through
          without ever competing with the text in front of it. */}
      <div className="absolute inset-0 bg-[var(--l-bg)]/78" />
    </div>
  );
}

function Layer({ isActive, children }: { isActive: boolean; children: React.ReactNode }) {
  return (
    <div
      className="absolute inset-0 flex items-center justify-center transition-all duration-[1500ms] ease-[cubic-bezier(0.16,1,0.3,1)]"
      style={{
        opacity: isActive ? 0.42 : 0,
        transform: isActive ? "scale(1) rotate(0deg)" : "scale(1.32) rotate(16deg)",
      }}
    >
      {children}
    </div>
  );
}
