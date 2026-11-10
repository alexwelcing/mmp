/**
 * Every network compiles to WGSL, and the result parses.
 *
 * This runs without a GPU. It proves the networks are valid shader source,
 * not that a GPU has run them: that check lives on the demo page.
 */
import { expect, test } from 'vitest';
import tgpu from 'typegpu';
// @ts-expect-error The package ships no types for this entry point.
import { WgslReflect } from 'wgsl_reflect/wgsl_reflect.module.js';
import { allWgsl } from './gpu.ts';
import { buildNetworks, PART_OF } from './networks.ts';

test('every network compiles to WGSL on its own', () => {
  const nets = buildNetworks(1);
  for (const [name, net] of Object.entries(nets)) {
    const code = tgpu.resolve([net]);
    expect(code.length, name).toBeGreaterThan(100);
    expect(code, name).toMatch(/fn \w+\(/);
  }
});

test('all networks compile into one module that an independent parser accepts', () => {
  const nets = buildNetworks(1);
  const parsed = new WgslReflect(allWgsl(nets));
  const names: string[] = parsed.functions.map((f: { name: string }) => f.name);
  for (const expected of ['perceive', 'mind', 'speech', 'body', 'contact', 'impulse', 'stepBody', 'outcome', 'director', 'light', 'choose', 'within', 'noGain']) {
    expect(names, expected).toContain(expected);
  }
});

test('all five parts of the game have at least one network', () => {
  const parts = new Set(Object.values(PART_OF));
  expect([...parts].sort()).toEqual(['characters', 'mechanics', 'physics', 'plot', 'world']);
});
