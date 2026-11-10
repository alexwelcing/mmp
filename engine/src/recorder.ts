/**
 * The recorder: every call to every network is captured, so any network can
 * be replayed alone against real play. See Spec 2, "The recorder".
 *
 * Stage 1 keeps the live typed values in a ring in memory. The binary file
 * layout in the spec comes with the storage worker.
 */
import type { Networks } from './networks.ts';
import { fingerprints } from './schema.ts';

export interface Call {
  tick: number;
  network: keyof Networks;
  inputs: unknown[];
  output: unknown;
}

/** Ten seconds of ticks. */
export const RING_TICKS = 600;

export class Recorder {
  readonly header: { seed: number; fingerprints: Record<string, string> };
  private ring: Call[][] = [];
  private current: Call[] = [];

  constructor(seed: number) {
    this.header = { seed, fingerprints: fingerprints() };
  }

  record(call: Call): void {
    this.current.push(call);
  }

  /** Close the tick being recorded. The oldest tick falls out of the ring. */
  endTick(): void {
    this.ring.push(this.current);
    this.current = [];
    if (this.ring.length > RING_TICKS) {
      this.ring.shift();
    }
  }

  get ticks(): readonly Call[][] {
    return this.ring;
  }

  calls(network?: keyof Networks): Call[] {
    const all = this.ring.flat();
    return network ? all.filter((c) => c.network === network) : all;
  }
}

/**
 * Wrap every network so each call is recorded. The wrapped networks have the
 * same types as the originals, so the tick cannot tell the difference.
 */
export function recording(nets: Networks, recorder: Recorder, tickOf: () => number): Networks {
  const wrapped: Record<string, unknown> = {};
  for (const [name, net] of Object.entries(nets)) {
    const call = net as (...args: unknown[]) => unknown;
    wrapped[name] = (...inputs: unknown[]) => {
      const output = call(...inputs);
      recorder.record({ tick: tickOf(), network: name as keyof Networks, inputs, output });
      return output;
    };
  }
  return wrapped as unknown as Networks;
}

/** Typed values print as plain numbers, so equal values give equal text. */
export function asText(value: unknown): string {
  return JSON.stringify(value, (_key, v) => (ArrayBuffer.isView(v) ? Array.from(v as never) : v));
}

/**
 * Replay recorded calls through a set of networks and count how many outputs
 * differ. On the same networks the answer is 0. On retrained networks it is
 * the measure of what changed.
 */
export function replay(nets: Networks, calls: Call[]): { total: number; different: number } {
  let different = 0;
  for (const c of calls) {
    const net = nets[c.network] as unknown as (...args: unknown[]) => unknown;
    if (asText(net(...c.inputs)) !== asText(c.output)) {
      different += 1;
    }
  }
  return { total: calls.length, different };
}
