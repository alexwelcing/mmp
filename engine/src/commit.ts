/**
 * Phase 6 of the tick: the commit.
 *
 * This is the one phase that runs no network. It applies typed Moves to the
 * Counts and Facts tables by whole-number arithmetic, in a fixed order. Every
 * decision about what a move should be was made by the outcome network; this
 * only applies it. See Spec 2, "Moves are applied in a fixed order".
 */
import { CAP, ITEM, MOVE } from './capacities.ts';
import type { Move } from './schema.ts';

export interface CommitResult {
  counts: Uint32Array;
  facts: number;
  applied: number;
  voided: number;
}

const HEALTH_CAP = 100;

/** Moves are sorted by taker, then kind, then giver, so order never varies. */
export function sortMoves(moves: Move[]): Move[] {
  return [...moves].sort(
    (p, q) => p.taker - q.taker || p.kind - q.kind || p.giver - q.giver || p.item - q.item,
  );
}

export function commitMoves(countsIn: Uint32Array, factsIn: number, moves: Move[]): CommitResult {
  const counts = new Uint32Array(countsIn); // read old, write new
  let facts = factsIn >>> 0;
  let applied = 0;
  let voided = 0;
  const at = (entity: number, item: number): number => entity * CAP.items + item;

  for (const move of sortMoves(moves)) {
    const { kind, giver, taker, item, amount } = move;
    let ok = true;

    if (kind === MOVE.none) {
      continue;
    } else if (kind === MOVE.transfer) {
      // Void if the giver does not hold that much. Counts never go negative.
      // Health is not handed over: it changes only by damage and restore.
      ok =
        item !== ITEM.none &&
        item !== ITEM.health &&
        amount > 0 &&
        giver !== taker &&
        counts[at(giver, item)] >= amount;
      if (ok) {
        counts[at(giver, item)] -= amount;
        counts[at(taker, item)] += amount;
      }
    } else if (kind === MOVE.damage) {
      const health = counts[at(taker, ITEM.health)];
      counts[at(taker, ITEM.health)] = health - Math.min(health, amount);
    } else if (kind === MOVE.restore) {
      const health = counts[at(taker, ITEM.health)];
      counts[at(taker, ITEM.health)] = Math.min(HEALTH_CAP, health + amount);
    } else if (kind === MOVE.setFact) {
      facts = (facts | (1 << (item % CAP.facts))) >>> 0;
    } else if (kind === MOVE.clearFact) {
      facts = (facts & ~(1 << (item % CAP.facts))) >>> 0;
    } else if (kind === MOVE.appear) {
      ok = item !== ITEM.none && item !== ITEM.health;
      if (ok) {
        counts[at(taker, item)] += amount;
      }
    } else if (kind === MOVE.vanish) {
      ok = item !== ITEM.none && item !== ITEM.health && counts[at(taker, item)] >= amount;
      if (ok) {
        counts[at(taker, item)] -= amount;
      }
    } else {
      ok = false; // not a move kind: cannot come from a Choice of 8, but be safe
    }

    if (ok) {
      applied += 1;
    } else {
      voided += 1;
    }
  }

  return { counts, facts, applied, voided };
}
