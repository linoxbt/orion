/**
 * The photography behind the landing page's hero.
 *
 * Real, properly-licensed images (Unsplash License: free commercial use, no
 * attribution required), chosen for what this product is actually about -
 * statements, invoices, receipts, the paperwork a bill arrives as - rather
 * than anything abstractly "AI".
 *
 * `alt` is deliberately empty: these are decorative watermarks sitting behind
 * real text, and a screen reader announcing a stack of photo descriptions
 * behind a headline is noise, not information.
 */
export interface LandingImage {
  src: string;
  alt: string;
  /** What it is, for whoever edits this file next. */
  note: string;
}

export const HERO_IMAGES: LandingImage[] = [
  {
    src: "https://images.unsplash.com/photo-1554224155-6726b3ff858f",
    alt: "",
    note: "invoices and paperwork",
  },
  {
    src: "https://images.unsplash.com/photo-1587560699334-cc4ff634909a",
    alt: "",
    note: "statements on a desk",
  },
  {
    src: "https://images.unsplash.com/photo-1423666639041-f56000c27a9a",
    alt: "",
    note: "printed receipts",
  },
  {
    src: "https://images.unsplash.com/photo-1450101499163-c8848c66ca85",
    alt: "",
    note: "working through the post at a desk",
  },
];

/** The three full-width reveals down the page, in order. */
export const REVEAL_IMAGES = {
  call: "https://images.unsplash.com/photo-1450101499163-c8848c66ca85",
  bill: "https://images.unsplash.com/photo-1554224155-6726b3ff858f",
  receipt: "https://images.unsplash.com/photo-1556742049-0cfed4f6a45d",
} as const;
