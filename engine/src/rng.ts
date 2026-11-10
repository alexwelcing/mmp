/**
 * Counted randomness.
 *
 * Nothing in the engine carries hidden random state. A random number is a
 * hash of (seed, tick, row, stream), so any row of any tick can be recomputed
 * on its own. See Spec 2, "Repeatability and random numbers".
 */

/** A small seeded generator, used only to fill starting weights and worlds. */
export function mulberry32(seed: number): () => number {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/** A float in [0, 1) that depends only on its four arguments. */
export function counted(seed: number, tick: number, row: number, stream: number): number {
  let h = seed >>> 0;
  for (const v of [tick, row, stream]) {
    h = Math.imul(h ^ (v >>> 0), 0x9e3779b1) >>> 0;
    h = (h ^ (h >>> 15)) >>> 0;
  }
  h = Math.imul(h ^ (h >>> 13), 0x85ebca6b) >>> 0;
  return ((h ^ (h >>> 16)) >>> 0) / 4294967296;
}
