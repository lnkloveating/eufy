import { useEffect, useRef, useState } from "react";

/** Tracks the user's `prefers-reduced-motion` setting, updating live. */
export function usePrefersReducedMotion(): boolean {
  const [reduced, setReduced] = useState<boolean>(() => {
    if (typeof window === "undefined" || !window.matchMedia) return false;
    return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  });

  useEffect(() => {
    if (typeof window === "undefined" || !window.matchMedia) return;
    const media = window.matchMedia("(prefers-reduced-motion: reduce)");
    const onChange = () => setReduced(media.matches);
    media.addEventListener("change", onChange);
    return () => media.removeEventListener("change", onChange);
  }, []);

  return reduced;
}

/**
 * Smoothly tween an integer toward `value`. The final rendered value is always
 * exactly `value` (no fabricated drift). Honors reduced-motion (jumps instantly).
 *
 * A `setTimeout` fallback guarantees the target value is shown even when
 * `requestAnimationFrame` is throttled/paused (background tab or a non-composited
 * pane), so ledger numbers never get stuck mid-tween.
 */
export function useCountUp(value: number, duration = 450): number {
  const reduced = usePrefersReducedMotion();
  const [display, setDisplay] = useState(value);
  const raf = useRef(0);

  useEffect(() => {
    if (reduced) {
      setDisplay(value);
      return;
    }
    const from = display;
    if (from === value) return;
    const start = performance.now();
    const step = (now: number) => {
      const t = Math.min(1, (now - start) / duration);
      const eased = 1 - Math.pow(1 - t, 3);
      if (t < 1) {
        setDisplay(from + (value - from) * eased);
        raf.current = requestAnimationFrame(step);
      } else {
        setDisplay(value);
      }
    };
    raf.current = requestAnimationFrame(step);
    // Guarantee the endpoint even if rAF never fires.
    const settle = window.setTimeout(() => setDisplay(value), duration + 250);
    return () => {
      cancelAnimationFrame(raf.current);
      window.clearTimeout(settle);
    };
    // `display` intentionally read as a snapshot; re-running only on value change.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value, reduced, duration]);

  return Math.round(reduced ? value : display);
}
