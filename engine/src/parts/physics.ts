/**
 * The Physics part: the contact network and the step network.
 *
 * The step network proposes each body's next momentum. Its Bounded last layer
 * then guarantees two things whatever the weights are: nothing ends up below
 * the ground, and nothing carries more energy than the forces on it could
 * have given. See Spec 3, "Physics".
 *
 * Not built yet: message passing among many touching bodies (impulses are
 * worked out pair by pair for now), cloth and soft detail, and the sound
 * network. The floor is a flat plane at height 0.
 */
import tgpu, { d, std } from 'typegpu';
import { CELL_SIZE, GRAVITY, PHYSICS_STEPS, TICK_HZ } from '../capacities.ts';
import { noGain, unit, zeroToOne } from '../kinds.ts';
import { makeMlp } from '../mlp.ts';
import { Body, ContactGeometry, Vec } from '../schema.ts';

export const STEP_SECONDS = 1 / (TICK_HZ * PHYSICS_STEPS);

/** Contact: distance and direction between two nearby bodies. */
export function makeContact(seed: number) {
  const net = makeMlp('contact', seed);
  return tgpu
    .fn([Body, Body, d.vec3f], ContactGeometry)((a, b, apart) => {
      'use gpu';
      const x = Vec();
      x[0] = apart.x * 0.5;
      x[1] = apart.y * 0.5;
      x[2] = apart.z * 0.5;
      x[3] = a.radius;
      x[4] = b.radius;
      for (let i = 0; i < 5; i++) {
        x[5 + i] = a.shape[i];
        x[10 + i] = b.shape[i];
      }
      const y = net(x);
      return ContactGeometry({
        distance: 2 * std.tanh(y[0]),
        direction: unit(d.vec3f(y[1], y[2], y[3])),
      });
    })
    .$name('contact');
}

/**
 * Impulse: how hard two touching bodies push each other apart.
 *
 * The answer is Bounded between nothing and the most a perfectly bouncy
 * collision could exchange. The tick applies it to both bodies, equal and
 * opposite, so momentum is conserved whatever the weights are.
 */
export function makeImpulse(seed: number) {
  const net = makeMlp('impulse', seed);
  return tgpu
    .fn([ContactGeometry, Body, Body], d.f32)((geometry, a, b) => {
      'use gpu';
      const va = std.mul(1 / a.mass, a.momentum);
      const vb = std.mul(1 / b.mass, b.momentum);
      const closing = std.max(std.dot(std.sub(va, vb), geometry.direction), 0);
      const reduced = (a.mass * b.mass) / (a.mass + b.mass);
      const x = Vec();
      x[0] = geometry.distance;
      x[1] = closing;
      x[2] = a.mass * 0.1;
      x[3] = b.mass * 0.1;
      for (let i = 0; i < 6; i++) {
        x[4 + i] = a.material[i];
        x[10 + i] = b.material[i];
      }
      const y = net(x);
      return zeroToOne(y[0]) * 2 * reduced * closing;
    })
    .$name('impulse');
}

/**
 * Step: advance one body by one physics step.
 *
 * `impulse` is what its contacts gave it this step and `force` is what its
 * own character asked for. Both arrive already gathered.
 */
export function makeStep(seed: number) {
  const net = makeMlp('step', seed);
  return tgpu
    .fn([Body, d.vec3f, d.vec3f], Body)((body, impulse, force) => {
      'use gpu';
      const height = d.f32(body.cell.y) * CELL_SIZE + body.offset.y;
      const x = Vec();
      x[0] = body.momentum.x / body.mass;
      x[1] = body.momentum.y / body.mass;
      x[2] = body.momentum.z / body.mass;
      x[3] = impulse.x * 0.1;
      x[4] = impulse.y * 0.1;
      x[5] = impulse.z * 0.1;
      x[6] = force.x * 0.01;
      x[7] = force.y * 0.01;
      x[8] = force.z * 0.01;
      x[9] = height;
      x[10] = body.mass * 0.1;
      x[11] = body.radius;
      for (let i = 0; i < 4; i++) {
        x[12 + i] = body.shape[i];
      }
      const y = net(x);

      // The network's proposal for the next momentum.
      const proposed = std.mul(body.mass * 5, d.vec3f(y[0], y[1], y[2]));

      // Bounded, "no gain". The most kinetic energy this body could hold after
      // the step is what its old momentum plus every push on it would give.
      const pushed = std.add(
        std.add(body.momentum, impulse),
        std.mul(STEP_SECONDS, std.add(force, d.vec3f(0, -GRAVITY * body.mass, 0))),
      );
      const allowed = std.dot(pushed, pushed) / (2 * body.mass);
      let momentum = noGain(proposed, body.mass, allowed);

      // Position follows from momentum.
      let offset = std.add(body.offset, std.mul(STEP_SECONDS / body.mass, momentum));

      // Bounded, "outside". Nothing ends a step below the floor.
      const newHeight = d.f32(body.cell.y) * CELL_SIZE + offset.y;
      if (newHeight < body.radius) {
        offset = d.vec3f(offset.x, offset.y + (body.radius - newHeight), offset.z);
        momentum = d.vec3f(momentum.x, std.max(momentum.y, 0), momentum.z);
      }

      return Body({
        cell: body.cell,
        offset: offset,
        orientation: body.orientation,
        momentum: momentum,
        spin: body.spin,
        mass: body.mass,
        inertia: body.inertia,
        radius: body.radius,
        shape: body.shape,
        material: body.material,
        parent: body.parent,
        flags: body.flags,
      });
    })
    .$name('stepBody'); // `step` is a WGSL builtin
}
