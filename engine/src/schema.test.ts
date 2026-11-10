import { expect, test } from 'vitest';
import { d } from 'typegpu';
import { Body, describe, fingerprint, fingerprints, Move } from './schema.ts';

test('a fingerprint follows field names, types and order', () => {
  expect(describe(Move)).toBe('{kind:u32,giver:u32,taker:u32,item:u32,amount:u32}');
  const same = d.struct({ kind: d.u32, giver: d.u32, taker: d.u32, item: d.u32, amount: d.u32 });
  const reordered = d.struct({ giver: d.u32, kind: d.u32, taker: d.u32, item: d.u32, amount: d.u32 });
  const retyped = d.struct({ kind: d.u32, giver: d.u32, taker: d.u32, item: d.u32, amount: d.f32 });
  expect(fingerprint(same)).toBe(fingerprint(Move));
  expect(fingerprint(reordered)).not.toBe(fingerprint(Move));
  expect(fingerprint(retyped)).not.toBe(fingerprint(Move));
});

test('every connection type has a fingerprint', () => {
  const all = fingerprints();
  expect(Object.keys(all).length).toBeGreaterThanOrEqual(16);
  expect(all.Body).toBe(fingerprint(Body));
  for (const value of Object.values(all)) {
    expect(value).toMatch(/^[0-9a-f]{8}$/);
  }
});
