/**
 * The GPU side, so far: every network compiled to one WGSL module, and a
 * check that the browser's GPU accepts it.
 *
 * Stage 1 runs the tick on the CPU reference. Dispatching each network as a
 * compute pass over GPU state buffers is the next stage. See Spec 5.
 */
import tgpu from 'typegpu';
import type { Networks } from './networks.ts';

/** All networks as one WGSL module. */
export function allWgsl(nets: Networks): string {
  return tgpu.resolve(Object.values(nets));
}

export interface GpuCheck {
  available: boolean;
  ok: boolean;
  adapter: string;
  halfPrecision: boolean;
  errors: string[];
}

/** Ask the GPU to compile every network. Runs in a browser with WebGPU. */
export async function compileOnGpu(nets: Networks): Promise<GpuCheck> {
  const none: GpuCheck = { available: false, ok: false, adapter: '', halfPrecision: false, errors: [] };
  if (typeof navigator === 'undefined' || !('gpu' in navigator)) {
    return { ...none, errors: ['WebGPU is not available in this browser.'] };
  }
  const adapter = await navigator.gpu.requestAdapter();
  if (!adapter) {
    return { ...none, errors: ['No GPU adapter was offered.'] };
  }
  const device = await adapter.requestDevice();
  const module = device.createShaderModule({ code: allWgsl(nets) });
  const info = await module.getCompilationInfo();
  const errors = info.messages
    .filter((m) => m.type === 'error')
    .map((m) => `line ${m.lineNum}: ${m.message}`);
  const result: GpuCheck = {
    available: true,
    ok: errors.length === 0,
    adapter: `${adapter.info.vendor} ${adapter.info.architecture}`.trim(),
    halfPrecision: adapter.features.has('shader-f16'),
    errors,
  };
  device.destroy();
  return result;
}
