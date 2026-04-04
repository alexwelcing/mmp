declare module "@mkkellogg/gaussian-splats-3d" {
  export interface ViewerOptions {
    cameraUp?: [number, number, number];
    initialCameraPosition?: [number, number, number];
    initialCameraLookAt?: [number, number, number];
    rootElement: HTMLElement;
    sphericalHarmonicsDegree?: number;
  }

  export interface SplatSceneOptions {
    showLoadingUI?: boolean;
    progressiveLoad?: boolean;
  }

  export class Viewer {
    constructor(options: ViewerOptions);
    addSplatScene(url: string, options?: SplatSceneOptions): Promise<void>;
    start(): void;
    dispose(): void;
  }
}
