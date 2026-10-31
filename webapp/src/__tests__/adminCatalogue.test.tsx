import { fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { catalogueCollectionsApi, glpiMatchesApi, systemCatalogueApi, workspacesApi } from "../api/client";
import type { MyWorkspace } from "../api/types";
import { AdminCataloguePage } from "../pages/admin/Catalogue";
import { renderWith } from "../test/render";

afterEach(() => vi.restoreAllMocks());

const ws = (id: string, over: Partial<MyWorkspace> = {}) => ({ id, name: id, is_global: false, created_at: "",
  can_read: true, can_create: true, can_modify: true, can_delete: true, ...over }) as MyWorkspace;

function collections() {
  vi.spyOn(catalogueCollectionsApi, "list").mockResolvedValue({ workspace_id: "acc", sources: [], collections: [], history: [] });
  vi.spyOn(catalogueCollectionsApi, "review").mockResolvedValue([]);
}

describe("Administration › Catalogue", () => {
  it("shows the catalogue workspace, what depends on it, its collections, and GLPI matching for a chosen workspace", async () => {
    vi.spyOn(systemCatalogueApi, "status").mockResolvedValue({
      designated: "acc", candidates: ["acc"], name: "Acceleratori-INFN",
      records: { "Product Model": 131, Vendor: 41 }, other_records: {}, not_shared: 0, shared_types: 144, own_types: 78,
      hanging: { btf: ["accelerator"], sparc: ["accelerator"] }, units: { euaps: 272 }, collections: {} });
    collections();
    vi.spyOn(workspacesApi, "listMine").mockResolvedValue([ws("acc", { role: "catalogue" }), ws("it-services")]);
    const run = vi.spyOn(glpiMatchesApi, "run").mockResolvedValue({
      status: "ran", proposals: 1, exact: 1, near: 0, ambiguous: [], unmatched: [] });
    renderWith(<AdminCataloguePage />);

    expect(await screen.findByText("131 Product Models, 41 Vendors")).toBeInTheDocument();
    expect(screen.getByText("btf, sparc")).toBeInTheDocument();
    expect(screen.getByText("(euaps 272)")).toBeInTheDocument();
    expect(await screen.findByRole("region", { name: "Collections" })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Catalogue collections" })).not.toBeInTheDocument();   // embedded

    const pick = await screen.findByLabelText("Workspace with GLPI devices");
    expect(screen.queryByRole("option", { name: /^acc / })).not.toBeInTheDocument();    // not the catalogue itself
    fireEvent.change(pick, { target: { value: "it-services" } });
    fireEvent.click(await screen.findByRole("button", { name: "Propose models" }));
    await waitFor(() => expect(run).toHaveBeenCalledWith("it-services"));
  });

  it("without a catalogue, offers to designate one", async () => {
    const status = vi.spyOn(systemCatalogueApi, "status").mockResolvedValue({ designated: null, candidates: ["acc"] });
    const designate = vi.spyOn(systemCatalogueApi, "designate").mockResolvedValue({
      designated: "acc", candidates: ["acc"], name: "Acc", records: {}, units: {}, hanging: {}, collections: {} });
    collections();
    vi.spyOn(workspacesApi, "listMine").mockResolvedValue([]);
    renderWith(<AdminCataloguePage />);

    expect(await screen.findByText("No catalogue workspace")).toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "Collections" })).not.toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Workspace to designate"), { target: { value: "acc" } });
    status.mockResolvedValue({ designated: "acc", candidates: ["acc"], name: "Acc", records: {}, units: {}, hanging: {}, collections: {} });
    fireEvent.click(screen.getByRole("button", { name: "Designate" }));
    await waitFor(() => expect(designate).toHaveBeenCalledWith("acc"));
    expect(await screen.findByRole("region", { name: "Collections" })).toBeInTheDocument();
  });
});
