/**
 * The step network's Bounded last layer holds for any weights and any input:
 * nothing ends below the floor, and nothing gains energy from nowhere.
 */
import { expect, test } from 'vitest';
import { d } from 'typegpu';
import { CELL_SIZE, GRAVITY } from './capacities.ts';
import { makeImpulse, makeStep, STEP_SECONDS } from './parts/physics.ts';
import { mulberry32 } from './rng.ts';
import { Body, ContactGeometry, WIDTH } from './schema.ts';

const rand = mulberry32(99);
const span = (r: number): number => rand() * 2 * r - r;

function randomBody(): Body {
  const radius = 0.05 + rand() * 0.5;
  return Body({
    cell: d.vec3i(0, 0, 0),
    offset: d.vec3f(span(20), radius + rand() * 3, span(20)),
    orientation: d.vec4f(0, 0, 0, 1),
    momentum: d.vec3f(span(50), span(50), span(50)),
    spin: d.vec3f(0, 0, 0),
    mass: 0.2 + rand() * 80,
    inertia: d.vec3f(1, 1, 1),
    radius,
    shape: Array.from({ length: WIDTH }, () => span(1)),
    material: Array.from({ length: 8 }, () => span(1)),
    parent: 0,
    flags: 0,
  });
}

test('after a step nothing is below the floor, for any weights', () => {
  for (let seed = 1; seed <= 5; seed++) {
    const step = makeStep(seed * 1000);
    for (let i = 0; i < 300; i++) {
      const next = step(randomBody(), d.vec3f(span(30), span(30), span(30)), d.vec3f(span(200), span(200), span(200)));
      const height = next.cell.y * CELL_SIZE + next.offset.y;
      expect(height).toBeGreaterThanOrEqual(next.radius - 1e-4);
    }
  }
});

test('a step never gives a body more energy than the pushes on it could', () => {
  for (let seed = 1; seed <= 5; seed++) {
    const step = makeStep(seed * 1000);
    for (let i = 0; i < 300; i++) {
      const body = randomBody();
      const impulse = [span(30), span(30), span(30)];
      const force = [span(200), span(200), span(200)];
      const next = step(body, d.vec3f(impulse[0], impulse[1], impulse[2]), d.vec3f(force[0], force[1], force[2]));
      const pushed = [
        body.momentum.x + impulse[0] + STEP_SECONDS * force[0],
        body.momentum.y + impulse[1] + STEP_SECONDS * (force[1] - GRAVITY * body.mass),
        body.momentum.z + impulse[2] + STEP_SECONDS * force[2],
      ];
      const allowed = (pushed[0] ** 2 + pushed[1] ** 2 + pushed[2] ** 2) / (2 * body.mass);
      const p = next.momentum;
      const kinetic = (p.x * p.x + p.y * p.y + p.z * p.z) / (2 * body.mass);
      expect(kinetic).toBeLessThanOrEqual(allowed * 1.001 + 1e-4);
    }
  }
});

test('a body left alone on the floor comes to rest and stays there', () => {
  const step = makeStep(123);
  let body = randomBody();
  for (let i = 0; i < 2000; i++) {
    body = step(body, d.vec3f(0, 0, 0), d.vec3f(0, 0, 0));
  }
  const speed = Math.hypot(body.momentum.x, body.momentum.y, body.momentum.z) / body.mass;
  expect(Number.isFinite(speed)).toBe(true);
  expect(body.cell.y * CELL_SIZE + body.offset.y).toBeGreaterThanOrEqual(body.radius - 1e-4);
});

test('an impulse is never negative and never more than a perfect bounce', () => {
  for (let seed = 1; seed <= 5; seed++) {
    const impulse = makeImpulse(seed * 77);
    for (let i = 0; i < 300; i++) {
      const a = randomBody();
      const b = randomBody();
      const dir = [span(1), span(1), span(1)];
      const len = Math.hypot(dir[0], dir[1], dir[2]) || 1;
      const direction = d.vec3f(dir[0] / len, dir[1] / len, dir[2] / len);
      const push = impulse(ContactGeometry({ distance: -rand(), direction }), a, b);
      const closing = Math.max(
        0,
        (a.momentum.x / a.mass - b.momentum.x / b.mass) * direction.x +
          (a.momentum.y / a.mass - b.momentum.y / b.mass) * direction.y +
          (a.momentum.z / a.mass - b.momentum.z / b.mass) * direction.z,
      );
      const most = (2 * a.mass * b.mass * closing) / (a.mass + b.mass);
      expect(push).toBeGreaterThanOrEqual(0);
      expect(push).toBeLessThanOrEqual(most * 1.001 + 1e-4);
    }
  }
});
