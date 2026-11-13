import { screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { BulkActionsBar } from "../components/BulkActionsBar";
import { DialogHost } from "../lib/dialogs";
import { renderWith } from "../test/render";

const base = { kind: "issue_uids" as const, label: "tickets", onStarted: vi.fn(), onClear: vi.fn() };
const cache = { '["me"]': { workspace_id: "ws" }, '["my-workspaces"]': [] };

describe("the bulk toolbar", () => {
  it("is not there while nothing is selected", () => {
    renderWith(<BulkActionsBar {...base} selected={new Set()} bulkDelete={vi.fn()} />, { cache });
    expect(screen.queryByRole("region", { name: /selected tickets/ })).toBeNull();
    expect(screen.queryByText(/Select tickets to/)).toBeNull();
  });

  it("appears with the selection and every action it allows", () => {
    renderWith(<BulkActionsBar {...base} selected={new Set(["a", "b"])} bulkDelete={vi.fn()} />, { cache });
    const bar = screen.getByRole("region", { name: "Actions on the selected tickets" });
    expect(bar).toHaveTextContent("2 selected");
    expect(screen.getByRole("button", { name: "Delete" })).toBeInTheDocument();
    expect(screen.getByLabelText("Copy or move")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Clear selection" })).toBeInTheDocument();
  });

  it("offers only what the person may do", () => {
    renderWith(<BulkActionsBar {...base} selected={new Set(["a"])} canTransfer={false} />, { cache });
    expect(screen.queryByRole("button", { name: "Delete" })).toBeNull();
    expect(screen.queryByLabelText("Copy or move")).toBeNull();
    expect(screen.getByRole("button", { name: "Clear selection" })).toBeInTheDocument();
  });

  it("asks before deleting, in the app's own dialog", async () => {
    const del = vi.fn().mockResolvedValue({ deleted: 1, not_found: [] });
    const native = vi.spyOn(window, "confirm");
    renderWith(<><BulkActionsBar {...base} selected={new Set(["a"])} bulkDelete={del} /><DialogHost /></>, { cache });
    screen.getByRole("button", { name: "Delete" }).click();
    const dialog = await screen.findByRole("dialog");
    expect(dialog).toHaveTextContent("Delete 1 tickets? This cannot be undone.");
    within(dialog).getByRole("button", { name: "Cancel" }).click();
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    expect(del).not.toHaveBeenCalled();
    screen.getByRole("button", { name: "Delete" }).click();
    within(await screen.findByRole("dialog")).getByRole("button", { name: "Yes, go ahead" }).click();
    await waitFor(() => expect(del).toHaveBeenCalled());
    expect(native).not.toHaveBeenCalled();
    native.mockRestore();
  });
});
