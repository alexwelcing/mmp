/**
 * The three kinds of type keep their promises for any input.
 * These are the guarantees the whole design rests on.
 */
import { expect, test } from 'vitest';
import { d } from 'typegpu';
import { choose, noGain, within } from './kinds.ts';
import { mulberry32 } from './rng.ts';
import { WIDTH } from './schema.ts';

const rand = mulberry32(42);
const scores = (): number[] => Array.from({ length: WIDTH }, () => rand() * 20 - 10);

test('a Choice never picks an option that is not allowed', () => {
  for (let i = 0; i < 2000; i++) {
    const count = 1 + Math.floor(rand() * WIDTH);
    const mask = (Math.floor(rand() * 65536) | 1) >>> 0; // option 0 is always on
    const pick = choose(scores(), count, mask);
    expect(pick).toBeLessThan(count);
    expect((mask >>> pick) & 1).toBe(1);
  }
});

test('a Choice takes the highest allowed score, lowest index on a tie', () => {
  const s = Array.from({ length: WIDTH }, () => 0);
  s[3] = 5;
  s[7] = 9;
  s[9] = 9;
  expect(choose(s, WIDTH, 0xffff)).toBe(7);
  expect(choose(s, WIDTH, 0xffff & ~(1 << 7))).toBe(9);
  expect(choose(s, WIDTH, 0b1001)).toBe(3);
  expect(choose(s, WIDTH, 0)).toBe(0); // empty mask falls back to "none"
});

test('"within" never returns a vector longer than the limit', () => {
  for (let i = 0; i < 2000; i++) {
    const limit = rand() * 300;
    const v = within(d.vec3f(rand() * 2000 - 1000, rand() * 2000 - 1000, rand() * 2000 - 1000), limit);
    expect(Math.hypot(v.x, v.y, v.z)).toBeLessThanOrEqual(limit * 1.0001 + 1e-6);
  }
});

test('"no gain" never returns more kinetic energy than allowed', () => {
  for (let i = 0; i < 2000; i++) {
    const mass = 0.1 + rand() * 100;
    const allowed = rand() * 500;
    const p = noGain(d.vec3f(rand() * 400 - 200, rand() * 400 - 200, rand() * 400 - 200), mass, allowed);
    const kinetic = (p.x * p.x + p.y * p.y + p.z * p.z) / (2 * mass);
    expect(kinetic).toBeLessThanOrEqual(allowed * 1.0001 + 1e-6);
  }
});
