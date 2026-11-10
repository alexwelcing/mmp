/**
 * The World part: for now, only the light network.
 *
 * It gives a visible thing its color under the region's current light. The
 * color is Bounded to 0..1 on every channel. See Spec 3, "World".
 *
 * Not built yet: the scene field, the form network, and weather and time.
 */
import tgpu, { d } from 'typegpu';
import { zeroToOne } from '../kinds.ts';
import { makeMlp } from '../mlp.ts';
import { LightInput, Vec } from '../schema.ts';

export function makeLight(seed: number) {
  const net = makeMlp('light', seed);
  return tgpu
    .fn([LightInput], d.vec3f)((p) => {
      'use gpu';
      const x = Vec();
      for (let i = 0; i < 8; i++) {
        x[i] = p.material[i];
      }
      x[8] = p.facing.x;
      x[9] = p.facing.y;
      x[10] = p.facing.z;
      x[11] = p.view.x;
      x[12] = p.view.y;
      x[13] = p.view.z;
      x[14] = p.light.x;
      x[15] = p.light.y;
      const y = net(x);
      return d.vec3f(zeroToOne(y[0]), zeroToOne(y[1]), zeroToOne(y[2]));
    })
    .$name('light');
}
