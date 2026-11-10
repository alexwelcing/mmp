/**
 * The three kinds of type, as last layers.
 *
 * Every network output is a Choice, a Move or a Bounded value. Each kind fixes
 * the network's last layer, and that layer is what makes an illegal value
 * impossible to express. See Spec 1, "The three kinds of type".
 *
 * These are 'use gpu' functions: the same source runs in JavaScript for tests
 * and compiles to WGSL for the GPU.
 */
import tgpu, { d, std } from 'typegpu';
import { Vec } from './schema.ts';

/**
 * Choice. Returns the highest-scoring option among the first `count` whose
 * mask bit is set, lowest index on a tie.
 *
 * Option 0 must always be allowed. It is the fallback when the mask is empty,
 * and every Choice in the game gives it the meaning "none".
 */
export const choose = tgpu
  .fn([Vec, d.u32, d.u32], d.u32)((scores, count, mask) => {
    'use gpu';
    let best = d.u32(0);
    let bestScore = d.f32(-1e30);
    for (let i = d.u32(0); i < count; i++) {
      const on = (mask >>> i) & 1;
      if (on === 1 && scores[i] > bestScore) {
        bestScore = scores[i];
        best = i;
      }
    }
    return best;
  })
  .$name('choose');

/** Bounded, "within": scale a vector down to a stated maximum length. */
export const within = tgpu
  .fn([d.vec3f, d.f32], d.vec3f)((v, limit) => {
    'use gpu';
    const len = std.length(v);
    const scale = std.min(1, limit / std.max(len, 1e-6));
    return std.mul(scale, v);
  })
  .$name('within');

/**
 * Bounded, "no gain": scale a momentum down until its kinetic energy is no
 * more than the energy the step was allowed.
 */
export const noGain = tgpu
  .fn([d.vec3f, d.f32, d.f32], d.vec3f)((momentum, mass, allowedKinetic) => {
    'use gpu';
    const kinetic = std.dot(momentum, momentum) / (2 * mass);
    let scale = d.f32(1);
    if (kinetic > allowedKinetic) {
      scale = std.sqrt(std.max(allowedKinetic, 0) / std.max(kinetic, 1e-12));
    }
    return std.mul(scale, momentum);
  })
  .$name('noGain');

/** A unit vector, or straight up when the input has no direction. */
export const unit = tgpu
  .fn([d.vec3f], d.vec3f)((v) => {
    'use gpu';
    const len = std.length(v);
    let out = d.vec3f(0, 1, 0);
    if (len > 1e-6) {
      out = std.mul(1 / len, v);
    }
    return out;
  })
  .$name('unit');

/** Squash any number into 0..1. */
export const zeroToOne = tgpu
  .fn([d.f32], d.f32)((x) => {
    'use gpu';
    return 0.5 + 0.5 * std.tanh(x);
  })
  .$name('zeroToOne');
