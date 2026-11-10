/**
 * Every network in the game, built from one seed.
 *
 * This is the single list the tick, the recorder, the tests and the GPU
 * compile check all read from. When the factory exists it will produce this
 * same shape from trained weights.
 */
import { makeBody, makeMind, makePerceive, makeSpeech } from './parts/characters.ts';
import { makeOutcome } from './parts/mechanics.ts';
import { makeContact, makeImpulse, makeStep } from './parts/physics.ts';
import { makeDirector } from './parts/plot.ts';
import { makeLight } from './parts/world.ts';

export function buildNetworks(seed: number) {
  return {
    // Characters
    perceive: makePerceive(seed + 100),
    mind: makeMind(seed + 200),
    speech: makeSpeech(seed + 300),
    body: makeBody(seed + 400),
    // Physics
    contact: makeContact(seed + 500),
    impulse: makeImpulse(seed + 550),
    step: makeStep(seed + 600),
    // Mechanics
    outcome: makeOutcome(seed + 700),
    // Plot
    director: makeDirector(seed + 800),
    // World
    light: makeLight(seed + 900),
  };
}

export type Networks = ReturnType<typeof buildNetworks>;

/** Which part of the game each network belongs to. */
export const PART_OF: Record<keyof Networks, string> = {
  perceive: 'characters',
  mind: 'characters',
  speech: 'characters',
  body: 'characters',
  contact: 'physics',
  impulse: 'physics',
  step: 'physics',
  outcome: 'mechanics',
  director: 'plot',
  light: 'world',
};
