/**
 * @vitest-environment jsdom
 *
 * The loading state is the app's most-seen component and the one that hid two
 * separate bugs: a page that never resolved looked exactly like a page that
 * was working. It must at least announce itself to a screen reader, and say
 * what it is waiting for.
 */

import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Loading } from "./loading";

describe("Loading", () => {
  it("announces itself rather than spinning silently", () => {
    render(<Loading />);
    const status = screen.getByRole("status");
    expect(status).toBeTruthy();
    expect(status.getAttribute("aria-live")).toBe("polite");
  });

  it("says what it is waiting for", () => {
    render(<Loading label="Loading negotiations" />);
    expect(screen.getByText("Loading negotiations")).toBeTruthy();
  });

  it("defaults to a label rather than none", () => {
    render(<Loading />);
    expect(screen.getByText("Loading")).toBeTruthy();
  });
});
