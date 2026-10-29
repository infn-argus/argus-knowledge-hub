import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { aiApi } from "../api/client";
import { Ask } from "../pages/ai/Ask";
import { renderWith } from "../test/render";

const chat = vi.hoisted(() => vi.fn());
vi.mock("../api/client", async (original) => ({ ...(await original<typeof import("../api/client")>()), streamChat: chat }));
vi.mock("../api/useCurrentWorkspaceId", () => ({ useCurrentWorkspaceId: () => "ws" }));

// jsdom lays nothing out: the page scrolls to its last turn.
Element.prototype.scrollIntoView = () => undefined;

afterEach(() => vi.restoreAllMocks());

const cache = { '["ai-status"]': { validated: true, enabled: true, has_vision: true }, '["ask-conversations"]': [] };

describe("a question with a file", () => {
  it("reads the file, sends its text with the question and shows it on the question", async () => {
    const read = vi.spyOn(aiApi, "readAttachment").mockResolvedValue(
      { name: "MoxaConfiguration.png", format: "image", text: "| Port 4 | VITARA+flame | 57600 |" });
    chat.mockResolvedValue(undefined);
    renderWith(<Ask />, { path: "/ask", cache });
    const png = new File([new Uint8Array([137, 80, 78, 71])], "MoxaConfiguration.png", { type: "image/png" });
    await userEvent.upload(screen.getByTestId("ask-file"), png);
    expect(read).toHaveBeenCalledWith(png);
    expect(await screen.findByText(/read by the vision model/)).toBeInTheDocument();
    await userEvent.type(screen.getByRole("textbox"), "What is on port 4?");
    await userEvent.click(screen.getByRole("button", { name: "Send" }));
    expect(chat).toHaveBeenCalledWith(
      { question: "What is on port 4?", conversation_id: null,
        attachments: [{ name: "MoxaConfiguration.png", format: "image", text: "| Port 4 | VITARA+flame | 57600 |" }] },
      expect.any(Function), expect.any(AbortSignal));
    expect(screen.getByText("MoxaConfiguration.png")).toBeInTheDocument();          // on the question sent
    expect(screen.queryByRole("list", { name: "Attached files" })).toBeNull();        // the composer is clear
  });

  it("sends a file alone", async () => {
    vi.spyOn(aiApi, "readAttachment").mockResolvedValue({ name: "list.csv", format: "csv", text: "a,b" });
    chat.mockResolvedValue(undefined);
    renderWith(<Ask />, { path: "/ask", cache });
    expect(screen.getByRole("button", { name: "Send" })).toBeDisabled();
    await userEvent.upload(screen.getByTestId("ask-file"), new File(["a,b"], "list.csv", { type: "text/csv" }));
    await screen.findByText(/3 characters/);
    await userEvent.click(screen.getByRole("button", { name: "Send" }));
    expect(chat.mock.lastCall![0]).toMatchObject({ question: "", attachments: [{ name: "list.csv" }] });
  });
});
