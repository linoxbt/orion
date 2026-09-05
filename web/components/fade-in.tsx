"use client";

import { motion } from "framer-motion";
import type { ReactNode } from "react";

/**
 * A fade-and-rise, either on mount or the first time the element is scrolled
 * into view.
 *
 * Use `onMount` for anything that wraps a whole page. A scroll-triggered fade
 * starts at opacity 0 and depends on a viewport callback to become visible, so
 * anything that stops that callback firing leaves the entire page blank -
 * which is precisely what happened here: the viewport threshold was a fraction
 * of the element, and an element several screens tall can never have 30% of
 * itself on screen at once.
 */
export function FadeIn({
  children,
  delay = 0,
  onMount = false,
}: {
  children: ReactNode;
  delay?: number;
  onMount?: boolean;
}) {
  const transition = { duration: 0.5, delay, ease: [0.16, 1, 0.3, 1] as const };
  const visible = { opacity: 1, y: 0 };

  if (onMount) {
    return (
      <motion.div initial={{ opacity: 0, y: 16 }} animate={visible} transition={transition}>
        {children}
      </motion.div>
    );
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      whileInView={visible}
      // "some", not a fraction: `amount: 0.3` waits for 30% of this element to
      // be on screen, which a tall one can never satisfy.
      viewport={{ once: true, amount: "some" }}
      transition={transition}
    >
      {children}
    </motion.div>
  );
}
