/**
 * The demo page: the whole tick running in a browser tab.
 *
 * It runs the CPU reference tick sixty times a second, draws every body from
 * above in the color the light network gave it, and shows what the people are
 * saying. It also asks the GPU to compile every network.
 *
 * The networks are untrained, so nothing here behaves sensibly yet. What the
 * page shows is that all five parts run together and the books stay straight.
 */
import { CAP, ITEM } from './capacities.ts';
import { compileOnGpu } from './gpu.ts';
import { buildNetworks } from './networks.ts';
import { count, createWorld, position } from './state.ts';
import type { World } from './state.ts';
import { tick } from './tick.ts';

/** The stand-in lexicon: what each word piece prints as. */
const LEXICON = ['.', 'well', 'met', 'friend', 'the', 'road', 'is', 'long', 'tonight', 'aye', 'no', 'gold'];

const SEED = 7;
const nets = buildNetworks(SEED);
let world: World = createWorld(1);

const canvas = document.getElementById('view') as HTMLCanvasElement;
const ctx = canvas.getContext('2d')!;
const status = document.getElementById('status')!;
const people = document.getElementById('people')!;
const gpu = document.getElementById('gpu')!;

function nameOf(entity: number): string {
  const person = world.characters.find((p) => p.root === entity);
  return person ? person.name : `thing ${entity}`;
}

function draw(tickMs: number): void {
  const scale = canvas.width / 14; // show 14 metres across
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  for (let e = 1; e < world.bodies.length; e++) {
    const [x, , z] = position(world.bodies[e]);
    const color = world.colors[e];
    ctx.fillStyle = `rgb(${color.x * 255}, ${color.y * 255}, ${color.z * 255})`;
    ctx.beginPath();
    ctx.arc(canvas.width / 2 + x * scale, canvas.height / 2 + z * scale, Math.max(3, world.bodies[e].radius * scale), 0, 2 * Math.PI);
    ctx.fill();
  }
  ctx.fillStyle = '#ddd';
  for (let c = 1; c < world.characters.length; c++) {
    const [x, , z] = position(world.bodies[world.characters[c].root]);
    ctx.fillText(world.characters[c].name, canvas.width / 2 + x * scale + 8, canvas.height / 2 + z * scale - 8);
  }

  const played = world.story.beats.filter((_, i) => (world.story.happened >>> i) & 1).map((b) => b.name);
  status.textContent =
    `tick ${world.tick}   ${tickMs.toFixed(1)} ms a tick on the CPU reference\n` +
    `beats played: ${played.join(', ') || 'none yet'}\n` +
    `facts: ${world.facts.toString(2).padStart(4, '0')}   contacts: ${world.contacts.length}   void moves: ${world.voidMoves}`;

  people.textContent = world.characters
    .slice(1)
    .map((p) => {
      const words = p.spoken
        .map((piece) => (piece < CAP.vocab ? LEXICON[piece] : `<${nameOf(p.say[piece - CAP.vocab])}>`))
        .join(' ');
      return `${p.name}  health ${count(world, p.root, ITEM.health)}  gold ${count(world, p.root, ITEM.gold)}\n  ${words}`;
    })
    .join('\n');
}

function frame(): void {
  const t0 = performance.now();
  world = tick(world, nets);
  draw(performance.now() - t0);
  requestAnimationFrame(frame);
}

compileOnGpu(nets).then((check) => {
  gpu.className = check.ok ? 'ok' : 'bad';
  gpu.textContent = check.ok
    ? `GPU compiled every network (${check.adapter}; half precision ${check.halfPrecision ? 'available' : 'not available'}).`
    : `GPU check failed:\n${check.errors.join('\n')}`;
});

requestAnimationFrame(frame);
