"use client";

import { useEffect } from "react";
import { Ringback } from "./ringback";

/** Ring while `active`, and always stop on unmount.
 *
 * A ringback that outlives its call is worse than none at all, so teardown
 * runs on every dependency change rather than only when the tone is turned
 * off deliberately.
 */
export function useRingback(active: boolean): void {
  useEffect(() => {
    if (!active) return;

    const tone = new Ringback();
    void tone.start();
    return () => {
      void tone.stop();
    };
  }, [active]);
}
