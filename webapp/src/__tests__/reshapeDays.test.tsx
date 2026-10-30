import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { reshapeApi, templatesApi } from "../api/client";
import { DocumentReshape } from "../pages/documents/Reshape";
import { renderWith } from "../test/render";

vi.mock("../api/useCurrentWorkspaceId", () => ({ useCurrentWorkspaceId: () => "ws" }));

afterEach(() => vi.restoreAllMocks());

const LOG = "SPARC Running LOG\n\n26.10.2026\nBeam back at 14:00.\n\n16.10.2026\nKlystron 2 tripped.";
const cache = {
  '["schemas"]': [{ uid: "t-log", name: "Logbook Entry", applies_to: "documents", is_concrete: true }],
  '["my-workspaces"]': [],
};

describe("a running log of several days", () => {
  it("previews its first day, not the whole log", async () => {
    vi.spyOn(templatesApi, "list").mockResolvedValue([]);
    vi.spyOn(templatesApi, "resolve").mockResolvedValue(null as never);
    const preview = vi.spyOn(reshapeApi, "preview").mockReturnValue(new Promise(() => undefined));
    renderWith(<DocumentReshape />, { path: "/documents/reshape?document_type_uid=t-log", cache });
    await userEvent.type(screen.getAllByRole("textbox")[0], LOG.replace(/\n/g, "{enter}"));
    expect(await screen.findByText(/This text holds 2 days/)).toBeInTheDocument();
    await userEvent.click(screen.getByTestId("preview-first-day"));
    expect(preview.mock.lastCall![0].source).toMatchObject(
      { text: "26.10.2026\nBeam back at 14:00.", original_date: "2026-10-26" });
    expect(screen.getByRole("button", { name: /26\.10\.2026/, pressed: true })).toBeInTheDocument();
  });
});
