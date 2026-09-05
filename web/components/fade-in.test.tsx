/**
 * @vitest-environment jsdom
 *
 * The blank page.
 *
 * FadeIn starts at opacity 0 and animates in. When it wrapped a whole page and
 * waited for 30% of *itself* to be on screen, a page several viewports tall
 * could never satisfy that - so it stayed invisible. No error, no failed
 * request, just nothing.
 *
 * These tests pin the two properties that make that impossible to repeat: a
 * whole-page fade animates on mount, and the scroll-triggered variant asks for
 * "some" of the element rather than a fraction of it.
 */

import { readFileSync } from "node:fs";
import { join } from "node:path";

import { render, screen } from "@testing-library/react";
import { beforeAll, describe, expect, it } from "vitest";

import { FadeIn } from "./fade-in";

const source = readFileSync(join(process.cwd(), "components/fade-in.tsx"), "utf8");
// The comments in that file quote the old broken value, so they are stripped
// before asserting on what the code actually does.
const code = source
  .split("\n")
  .filter((line) => !line.trim().startsWith("//") && !line.trim().startsWith("*"))
  .join("\n");

beforeAll(() => {
  // jsdom has no IntersectionObserver, and framer-motion's whileInView needs
  // one. A stub that never fires is the honest simulation of an element that
  // has not been scrolled to.
  if (!("IntersectionObserver" in globalThis)) {
    class Stub {
      observe() {}
      unobserve() {}
      disconnect() {}
      takeRecords() {
        return [];
      }
    }
    Object.defineProperty(globalThis, "IntersectionObserver", { value: Stub, writable: true });
  }
});

describe("FadeIn", () => {
  it("renders its children", () => {
    render(
      <FadeIn onMount>
        <p>the whole dashboard</p>
      </FadeIn>
    );
    expect(screen.getByText("the whole dashboard")).toBeTruthy();
  });

  it("renders them in the scroll-triggered mode too", () => {
    render(
      <FadeIn>
        <p>a section</p>
      </FadeIn>
    );
    expect(screen.getByText("a section")).toBeTruthy();
  });

  it("never waits for a fraction of its own height", () => {
    // `amount: 0.3` on a tall element is the bug: it can never be met.
    expect(code).not.toMatch(/amount:\s*0?\.\d/);
    expect(code).toContain('amount: "some"');
  });

  it("offers a mount-triggered mode for whole pages", () => {
    expect(code).toContain("onMount");
    expect(code).toContain("animate={visible}");
  });
});
