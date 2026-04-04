/**
 * GaussianSplatViewer.tsx — High-performance WebGL Gaussian Splatting viewer.
 *
 * Uses @mkkellogg/gaussian-splats-3d under the hood.
 * No UI chrome, no frills: just a fast canvas that loads .ply files.
 */

import { useEffect, useRef } from "react";
import * as GaussianSplats3D from "@mkkellogg/gaussian-splats-3d";

interface GaussianSplatViewerProps {
  url: string;
}

export function GaussianSplatViewer({ url }: GaussianSplatViewerProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const viewerRef = useRef<GaussianSplats3D.Viewer | null>(null);

  useEffect(() => {
    if (!containerRef.current || !url) return;

    const container = containerRef.current;

    const viewer = new GaussianSplats3D.Viewer({
      cameraUp: [0, -1, 0],
      initialCameraPosition: [0, 0, 2.5],
      initialCameraLookAt: [0, 0, 0],
      rootElement: container,
      sphericalHarmonicsDegree: 0, // faster loading, still great quality
    });

    viewerRef.current = viewer;

    viewer
      .addSplatScene(url, {
        showLoadingUI: true,
        progressiveLoad: true,
      })
      .then(() => {
        viewer.start();
      })
      .catch((err: unknown) => {
        // eslint-disable-next-line no-console
        console.error("Failed to load splat scene:", err);
      });

    return () => {
      viewer.dispose();
      viewerRef.current = null;
    };
  }, [url]);

  return (
    <div
      ref={containerRef}
      style={{
        width: "100%",
        height: "100%",
        minHeight: "280px",
        borderRadius: "12px",
        overflow: "hidden",
        background: "#000",
      }}
    />
  );
}
