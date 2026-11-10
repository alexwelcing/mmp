import { defineConfig } from 'vitest/config';
import typegpu from 'unplugin-typegpu/vite';

// The typegpu plugin is what lets a 'use gpu' function run in JavaScript here
// and compile to WGSL for the GPU.
export default defineConfig({
  plugins: [typegpu({})],
  test: {
    include: ['src/**/*.test.ts'],
    // The CPU reference tick runs networks one row at a time, so the
    // thousand-tick tests take a while.
    testTimeout: 120_000,
  },
});
