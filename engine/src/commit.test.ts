/**
 * The commit applies typed moves by whole-number arithmetic. Whatever moves
 * the outcome network produces, the books stay straight.
 */
import { expect, test } from 'vitest';
import { AMOUNT_LADDER, CAP, ITEM, MOVE } from './capacities.ts';
import { commitMoves, sortMoves } from './commit.ts';
import { mulberry32 } from './rng.ts';
import { Move } from './schema.ts';

const rand = mulberry32(2024);
const pick = (n: number): number => Math.floor(rand() * n);

function randomMove(kinds: number[]): Move {
  return Move({
    kind: kinds[pick(kinds.length)],
    giver: 1 + pick(8),
    taker: 1 + pick(8),
    item: pick(CAP.items),
    amount: AMOUNT_LADDER[pick(AMOUNT_LADDER.length)],
  });
}

function startingCounts(): Uint32Array {
  const counts = new Uint32Array(CAP.entities * CAP.items);
  for (let e = 1; e <= 8; e++) {
    counts[e * CAP.items + ITEM.health] = 100;
    counts[e * CAP.items + ITEM.gold] = 10 + pick(40);
    counts[e * CAP.items + ITEM.key] = pick(2);
  }
  return counts;
}

const total = (counts: Uint32Array, item: number): number => {
  let sum = 0;
  for (let e = 0; e < CAP.entities; e++) {
    sum += counts[e * CAP.items + item];
  }
  return sum;
};

test('transfers conserve every total and never overdraw', () => {
  let counts = startingCounts();
  const gold = total(counts, ITEM.gold);
  const keys = total(counts, ITEM.key);
  let applied = 0;
  let voided = 0;
  for (let round = 0; round < 500; round++) {
    const moves = Array.from({ length: 12 }, () => randomMove([MOVE.none, MOVE.transfer]));
    const result = commitMoves(counts, 0, moves);
    counts = result.counts;
    applied += result.applied;
    voided += result.voided;
    expect(total(counts, ITEM.gold)).toBe(gold);
    expect(total(counts, ITEM.key)).toBe(keys);
    expect(total(counts, ITEM.health)).toBe(800); // health is never handed over
  }
  // The test is only meaningful if both outcomes really occurred.
  expect(applied).toBeGreaterThan(100);
  expect(voided).toBeGreaterThan(100);
});

test('no mix of moves can drive a count below zero or health above full', () => {
  let counts = startingCounts();
  const all = Object.values(MOVE);
  for (let round = 0; round < 500; round++) {
    const before = counts;
    const moves = Array.from({ length: 12 }, () => randomMove(all));
    const result = commitMoves(counts, 0, moves);
    counts = result.counts;
    for (let e = 1; e <= 8; e++) {
      expect(counts[e * CAP.items + ITEM.health]).toBeLessThanOrEqual(100);
    }
    // An unsigned count that went "below zero" would wrap to billions.
    for (const value of counts) {
      expect(value).toBeLessThan(1_000_000);
    }
    expect(before).not.toBe(counts); // read old, write new
  }
});

test('moves are applied in one fixed order whatever order they arrive in', () => {
  for (let round = 0; round < 200; round++) {
    const moves = Array.from({ length: 10 }, () => randomMove(Object.values(MOVE)));
    const shuffled = [...moves].sort(() => rand() - 0.5);
    const start = startingCounts();
    const one = commitMoves(start, 5, moves);
    const two = commitMoves(start, 5, shuffled);
    expect(Array.from(two.counts)).toEqual(Array.from(one.counts));
    expect(two.facts).toBe(one.facts);
    expect(sortMoves(shuffled).map((m) => m.kind)).toEqual(sortMoves(moves).map((m) => m.kind));
  }
});

test('fact moves set and clear single bits', () => {
  const set = commitMoves(new Uint32Array(CAP.entities * CAP.items), 0, [
    Move({ kind: MOVE.setFact, giver: 1, taker: 2, item: 3, amount: 0 }),
  ]);
  expect(set.facts).toBe(0b1000);
  const cleared = commitMoves(set.counts, set.facts, [
    Move({ kind: MOVE.clearFact, giver: 1, taker: 2, item: 3, amount: 0 }),
  ]);
  expect(cleared.facts).toBe(0);
});
