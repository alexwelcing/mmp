/**
 * The Mechanics part: the outcome network holds the rules of the game.
 *
 * It reads one event and the two parties to it, and writes a typed Move. It
 * can misjudge what should happen. It cannot express an illegal change: the
 * kind is a Choice under a mask, the parties are a Choice between the two
 * bodies in the event, and the amount is a Choice from a whole-number ladder.
 * See Spec 3, "Mechanics".
 */
import tgpu, { d } from 'typegpu';
import { AMOUNT_LADDER, CAP, MOVE } from '../capacities.ts';
import { choose } from '../kinds.ts';
import { makeMlp } from '../mlp.ts';
import { GameEvent, Move, Party, Vec } from '../schema.ts';

const amounts = tgpu
  .const(d.arrayOf(d.u32, AMOUNT_LADDER.length), [...AMOUNT_LADDER])
  .$name('amount_ladder');

const ALL_ITEMS = (1 << CAP.items) - 1;

export function makeOutcome(seed: number) {
  const trunk = makeMlp('outcome_trunk', seed);
  const kindHead = makeMlp('outcome_kind', seed + 1);
  const restHead = makeMlp('outcome_rest', seed + 2);

  return tgpu
    .fn([GameEvent, Party, Party], Move)((event, a, b) => {
      'use gpu';
      const x = Vec();
      x[0] = d.f32(event.isContact);
      x[1] = event.impulse * 0.1;
      x[2] = d.f32(event.action) * 0.1;
      x[3] = a.health;
      x[4] = a.gold * 0.1;
      x[5] = b.health;
      x[6] = b.gold * 0.1;
      x[7] = d.f32(a.flags & 1);
      x[8] = d.f32(b.flags & 1);
      const core = trunk(x);
      const kindScores = kindHead(core);
      const rest = restHead(core);

      // Kind: a Choice under the mask the tick worked out for this event.
      const kind = choose(kindScores, 8, event.allowed);

      // Parties: a Choice between the two bodies in the event, never a third.
      let giver = event.a;
      let taker = event.b;
      if (rest[0] < 0) {
        giver = event.b;
        taker = event.a;
      }

      // Item: a Choice among item kinds. For fact moves, a Choice of fact.
      const itemScores = Vec();
      for (let k = 0; k < CAP.items; k++) {
        itemScores[k] = rest[1 + k];
      }
      let item = choose(itemScores, CAP.items, d.u32(ALL_ITEMS));
      if (kind === MOVE.setFact || kind === MOVE.clearFact) {
        item = choose(core, 16, 0xffff);
      }

      // Amount: a Choice from the whole-number ladder.
      const amountScores = Vec();
      for (let k = 0; k < 8; k++) {
        amountScores[k] = rest[5 + k];
      }
      const amount = amounts.$[choose(amountScores, 8, 0xff)];

      return Move({ kind: kind, giver: giver, taker: taker, item: item, amount: amount });
    })
    .$name('outcome');
}
