/**
 * The stand-in network body.
 *
 * Stage 1 gives every part a real, tiny network with seeded random weights:
 * one hidden layer of 16, as a typed function from Vec to Vec. Each part packs
 * its typed inputs into a Vec, runs one or more of these, and finishes with
 * the last layer its output type demands.
 *
 * Nothing here is trained yet. The point of stage 1 is that the parts compose
 * and the types hold, with the factory replacing these weights later.
 *
 * Weights are a module constant for now, which works for a few hundred
 * numbers. Trained networks will read theirs from a GPU buffer instead.
 */
import tgpu, { d, std } from 'typegpu';
import { mulberry32 } from './rng.ts';
import { Vec, WIDTH } from './schema.ts';

/** Two 16 by 16 layers and their two biases. */
export const MLP_WEIGHTS = 2 * WIDTH * WIDTH + 2 * WIDTH;

export function makeMlp(name: string, seed: number) {
  const rand = mulberry32(seed);
  const values = Array.from({ length: MLP_WEIGHTS }, () => (rand() * 2 - 1) * 0.5);
  const w = tgpu.const(d.arrayOf(d.f32, MLP_WEIGHTS), values).$name(`${name}_weights`);

  return tgpu
    .fn([Vec], Vec)((x) => {
      'use gpu';
      const hidden = Vec();
      for (let i = 0; i < WIDTH; i++) {
        let acc = w.$[2 * WIDTH * WIDTH + i];
        for (let j = 0; j < WIDTH; j++) {
          acc += w.$[i * WIDTH + j] * x[j];
        }
        hidden[i] = std.tanh(acc);
      }
      const y = Vec();
      for (let i = 0; i < WIDTH; i++) {
        let acc = w.$[2 * WIDTH * WIDTH + WIDTH + i];
        for (let j = 0; j < WIDTH; j++) {
          acc += w.$[WIDTH * WIDTH + i * WIDTH + j] * hidden[j];
        }
        y[i] = acc;
      }
      return y;
    })
    .$name(`${name}_mlp`);
}
