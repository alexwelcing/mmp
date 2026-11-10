/**
 * Capacities and code widths.
 *
 * Every table has a fixed size so every buffer has a known size. These are
 * small development values. The proposed full-size defaults are in
 * docs/engine/spec-1-types-and-state.md (16,384 entities, 1,024 characters...).
 */
export const CAP = {
  /** Bodies of any kind: a goblet, a limb, a person's root. */
  entities: 64,
  /** People and creatures. */
  characters: 8,
  /** Yes-or-no world facts. One 32-bit word for now. */
  facts: 32,
  /** Story beats. One 32-bit mask for now. Beat 0 always means "no beat". */
  beats: 16,
  /** Item kinds a count row can hold. */
  items: 4,
  /** Actions a mind can choose from. Action 0 is "do nothing". */
  actions: 8,
  /** Memory rows per character. */
  memoryRows: 4,
  /** Word pieces in the speech vocabulary. Piece 0 means "stay silent". */
  vocab: 12,
  /** Things a mind can hand to speech as references. */
  slots: 4,
} as const;

/** Item kinds. Health and gold are counts like any other. */
export const ITEM = { none: 0, health: 1, gold: 2, key: 3 } as const;

/** The eight kinds of move. See Spec 1, "The three kinds of type". */
export const MOVE = {
  none: 0,
  transfer: 1,
  damage: 2,
  restore: 3,
  setFact: 4,
  clearFact: 5,
  appear: 6,
  vanish: 7,
} as const;

/** The whole-number ladder a move's amount is chosen from. */
export const AMOUNT_LADDER = [0, 1, 2, 5, 10, 20, 50, 100] as const;

/** Body flags. */
export const FLAG = { character: 1, held: 2, asleep: 4 } as const;

/** A tick is one sixtieth of a second, with two physics steps inside it. */
export const TICK_HZ = 60;
export const PHYSICS_STEPS = 2;
/** Minds run 4 times a second: each character thinks every 15th tick. */
export const MIND_PERIOD = 15;
/** Speech emits 15 word pieces a second: every 4th tick. */
export const SPEECH_PERIOD = 4;
/** The director runs twice a second. */
export const PLOT_PERIOD = 30;

/** A position is a cell of this many metres plus an offset inside it. */
export const CELL_SIZE = 64;
export const GRAVITY = 9.81;
/** The most force a body network may ask of its character, in newtons. */
export const STRENGTH = 200;
