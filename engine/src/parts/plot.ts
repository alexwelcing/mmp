/**
 * The Plot part: the director chooses the next beat and who plays it.
 *
 * The beat is a Choice under the allowed mask, so only beats whose conditions
 * hold right now can be chosen. Beat 0 means "no beat now" and is always on
 * the list. See Spec 3, "Plot".
 */
import tgpu, { d, std } from 'typegpu';
import { CAP } from '../capacities.ts';
import { choose } from '../kinds.ts';
import { makeMlp } from '../mlp.ts';
import { BeatChoice, StoryInput, Vec, WIDTH } from '../schema.ts';

export function makeDirector(seed: number) {
  const trunk = makeMlp('director_trunk', seed);
  const beatHead = makeMlp('director_beat', seed + 1);
  const castHead = makeMlp('director_cast', seed + 2);

  return tgpu
    .fn([StoryInput], BeatChoice)((story) => {
      'use gpu';
      const x = Vec();
      for (let i = 0; i < WIDTH; i++) {
        const isAllowed = d.f32((story.allowed >>> d.u32(i)) & 1);
        const hasHappened = d.f32((story.happened >>> d.u32(i)) & 1);
        x[i] = 0.5 * story.state[i] + isAllowed - 0.5 * hasHappened;
      }
      x[0] += story.tension;
      x[1] += d.f32(story.nearby) * 0.1;
      const core = trunk(x);

      const beat = choose(beatHead(core), CAP.beats, story.allowed | 1);

      // Cast: a Choice among the characters who are near enough to play it.
      const count = std.min(story.nearby, 8);
      let castMask = (d.u32(1) << count) - 1;
      if (castMask === 0) {
        castMask = 1;
      }
      const actor = choose(castHead(core), 8, castMask);

      const state = Vec();
      for (let i = 0; i < WIDTH; i++) {
        state[i] = std.tanh(core[i]);
      }
      return BeatChoice({ beat: beat, actor: actor, state: state });
    })
    .$name('director');
}
