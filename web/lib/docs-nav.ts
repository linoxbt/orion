/**
 * The documentation's shape.
 *
 * One list, used by the sidebar, the search, the previous/next links at the
 * foot of every page, and the index cards. Keeping it in one place is what
 * stops the navigation and the pages themselves drifting apart, which is the
 * usual way a docs site starts lying about what it contains.
 */

export interface DocPage {
  slug: string;
  title: string;
  /** One line, shown on the index cards and in search results. */
  summary: string;
}

export interface DocSection {
  title: string;
  pages: DocPage[];
}

export const DOCS: DocSection[] = [
  {
    title: "Getting started",
    pages: [
      {
        slug: "",
        title: "Overview",
        summary: "What Orion does, and what it will never do on your behalf.",
      },
      {
        slug: "how-a-negotiation-works",
        title: "How a negotiation works",
        summary: "Six steps, from photographing a bill to a verified saving.",
      },
      {
        slug: "bill-types",
        title: "Bill types",
        summary: "Why the type you pick changes the entire argument.",
      },
    ],
  },
  {
    title: "On the call",
    pages: [
      {
        slug: "rehearsal-and-real-calls",
        title: "Rehearsal and real calls",
        summary: "Hear the agent over your microphone before it phones anyone.",
      },
      {
        slug: "playbooks",
        title: "The playbooks",
        summary: "The tactics it argues from, per provider and per vertical.",
      },
      {
        slug: "when-a-call-needs-you",
        title: "When a call needs you",
        summary: "How Orion reaches you mid-call, and how to set that up.",
      },
    ],
  },
  {
    title: "Trust",
    pages: [
      {
        slug: "authorisation",
        title: "Authorisation",
        summary: "What you agree to, what gets recorded, and why it is per bill.",
      },
      {
        slug: "verification",
        title: "How a saving is verified",
        summary: "The outcome is read off the recording, not self-reported.",
      },
      {
        slug: "recordings",
        title: "Call recordings",
        summary: "Every call is kept, playable and downloadable.",
      },
    ],
  },
  {
    title: "Account",
    pages: [
      {
        slug: "plans",
        title: "Plans and billing",
        summary: "Five bills a month free, or fifty cents for unlimited.",
      },
      {
        slug: "limits",
        title: "What it will not do",
        summary: "The lines the agent does not cross, on any call.",
      },
    ],
  },
];

/** Flat, in reading order - what previous/next and search walk. */
export const DOC_ORDER: DocPage[] = DOCS.flatMap((section) => section.pages);

export function docPath(slug: string): string {
  return slug ? `/docs/${slug}` : "/docs";
}

export function findDoc(slug: string): DocPage | undefined {
  return DOC_ORDER.find((page) => page.slug === slug);
}

export function neighbours(slug: string): { prev?: DocPage; next?: DocPage } {
  const i = DOC_ORDER.findIndex((page) => page.slug === slug);
  if (i === -1) return {};
  return { prev: DOC_ORDER[i - 1], next: DOC_ORDER[i + 1] };
}
