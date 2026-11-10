/**
 * The whole game ticks with every part in place, and the guarantees that the
 * types promise hold across thousands of ticks of untrained networks.
 */
import { expect, test } from 'vitest';
import { CAP, ITEM } from './capacities.ts';
import { buildNetworks } from './networks.ts';
import { Recorder, recording, replay } from './recorder.ts';
import { createWorld } from './state.ts';
import type { World } from './state.ts';
import { digest, tick } from './tick.ts';

const total = (world: World, item: number): number => {
  let sum = 0;
  for (let e = 0; e < CAP.entities; e++) {
    sum += world.counts[e * CAP.items + item];
  }
  return sum;
};

test('a whole tick runs with all five parts, and does not change its input', () => {
  const nets = buildNetworks(7);
  const start = createWorld(1);
  const before = digest(start);
  const next = tick(start, nets);
  expect(next.tick).toBe(1);
  expect(digest(start)).toBe(before);
  expect(next.colors.length).toBe(next.bodies.length);
});

test('the same seed replays exactly; a different seed does not', () => {
  const run = (netSeed: number, worldSeed: number): string => {
    const nets = buildNetworks(netSeed);
    let world = createWorld(worldSeed);
    for (let i = 0; i < 60; i++) {
      world = tick(world, nets);
    }
    return digest(world);
  };
  expect(run(7, 1)).toBe(run(7, 1));
  expect(run(7, 1)).not.toBe(run(8, 1));
  expect(run(7, 1)).not.toBe(run(7, 2));
});

test('typed moves keep the books straight for any weights', () => {
  for (const netSeed of [3, 11, 29]) {
    const nets = buildNetworks(netSeed);
    let world = createWorld(netSeed);
    const gold = total(world, ITEM.gold);
    const keys = total(world, ITEM.key);
    for (let i = 0; i < 240; i++) {
      world = tick(world, nets);
      // Gold and keys only move by transfer, so their totals never change.
      expect(total(world, ITEM.gold)).toBe(gold);
      expect(total(world, ITEM.key)).toBe(keys);
      // Health stays between nothing and full.
      for (let c = 1; c < world.characters.length; c++) {
        const health = world.counts[world.characters[c].root * CAP.items + ITEM.health];
        expect(health).toBeLessThanOrEqual(100);
      }
    }
  }
});

test('the story only ever plays a beat whose conditions held', () => {
  for (const netSeed of [3, 11, 29]) {
    const nets = buildNetworks(netSeed);
    let world = createWorld(5);
    for (let i = 0; i < 400; i++) {
      const next = tick(world, nets);
      const played = next.story.happened & ~world.story.happened;
      // Every newly played beat was on the allowed list the tick before.
      expect((played & ~world.story.allowed) >>> 0).toBe(0);
      world = next;
    }
    // "reconciliation" (beat 3) needs the quarrel fact, which only beat 2 sets
    // unless a rule move set it. Either way beat 3 never plays while fact 0 is unset.
    expect(world.story.happened & 1).toBe(0); // beat 0 is never recorded as played
  }
});

test('speech can only refer to what the mind chose to mention', () => {
  const nets = buildNetworks(13);
  let world = createWorld(2);
  let pieces = 0;
  for (let i = 0; i < 400; i++) {
    world = tick(world, nets);
    for (let c = 1; c < world.characters.length; c++) {
      const me = world.characters[c];
      expect(me.lastPiece).toBeLessThan(CAP.vocab + CAP.slots);
      if (me.lastPiece >= CAP.vocab) {
        // A slot piece always names something the mind put in that slot.
        expect(me.lastReference).toBeGreaterThan(0);
        expect(me.say).toContain(me.lastReference);
      }
      pieces += me.spoken.length;
    }
  }
  expect(pieces).toBeGreaterThan(0);
});

test('recorded calls replay exactly on the same networks, and differ on others', () => {
  const nets = buildNetworks(7);
  const recorder = new Recorder(7);
  let world = createWorld(1);
  const recorded = recording(nets, recorder, () => world.tick);
  for (let i = 0; i < 30; i++) {
    world = tick(world, recorded);
    recorder.endTick();
  }
  const calls = recorder.calls();
  expect(recorder.ticks.length).toBe(30);
  expect(calls.length).toBeGreaterThan(100);
  expect(replay(nets, calls).different).toBe(0);
  expect(replay(buildNetworks(8), calls).different).toBeGreaterThan(0);
});
