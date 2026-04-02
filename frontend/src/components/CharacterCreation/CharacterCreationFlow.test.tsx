import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";

import { CharacterCreationFlow } from "./CharacterCreationFlow";

describe("CharacterCreationFlow", () => {
  it("completes free-roll happy path and reaches reveal", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ job_id: "job-1", status: "queued" }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          job_id: "job-1",
          mode: "mock",
          stage: "complete",
          draft_urls: ["mock://draft/warrior-fantasy-0.png"],
          selected_draft_url: "mock://draft/warrior-fantasy-0.png",
          upscaled_url: "mock://upscaled/warrior-fantasy-0.png",
          threedgs_url: "mock://3dgs/warrior-fantasy-0.splat",
          audio_url: "mock://audio/warrior.wav",
          nft_token_id: null,
          error: null,
          stage_durations_ms: {},
          created_at_ms: Date.now(),
          updated_at_ms: Date.now(),
        }),
      });

    vi.stubGlobal("fetch", fetchMock);

    render(<CharacterCreationFlow />);
    await userEvent.click(screen.getByRole("button", { name: /generate my character/i }));

    await waitFor(() => {
      expect(screen.getByText(/meet/i)).toBeInTheDocument();
    });

    expect(fetchMock).toHaveBeenCalledTimes(2);
  });
});
