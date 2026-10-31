import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { packagesApi, type PackageInfo, type PackagePlan, type WorkspacePackageRow } from "../api/client";
import { AdminPackagesPage } from "../pages/admin/Packages";
import { WorkspacePackages } from "../pages/workspace/Packages";
import { renderWith } from "../test/render";

afterEach(() => vi.restoreAllMocks());

const row = (id: string, over: Partial<WorkspacePackageRow> = {}): WorkspacePackageRow => ({
  package_id: id, name: id, version: "2.0.0", checksum: "c".repeat(64), options: null, installed_at: null,
  installed_by: null, shipped_version: "2.0.0", upgrade_available: false, revert_to: [], ...over,
});

const info = (id: string, over: Partial<PackageInfo> = {}): PackageInfo => ({
  id, name: id, version: "1.0.0", description: `${id} description`, owner: "INFN", depends: {}, provides: [],
  checksum: "x", contents: { object_types: 3 }, installable: true, ...over,
});

const change = { id: "object_types/Pump/attributes/speed/removed", category: "breaking" as const, area: "object_types",
                 subject: "Pump", element: "speed", what: "removed", detail: "attribute 'speed' removed",
                 conflict: null, records: 2, violations: 0, actions: ["apply" as const, "keep" as const] };

const plan = (action: string, from: string, version: string): PackagePlan => ({
  workspace_id: "ws", options: {}, changes: true,
  steps: [{ package_id: "core-objects", version, checksum: "y", action, from_version: from, requested: true,
            result: { changes: [change], needs_decision: [change.id] } }],
});

function page() {
  return renderWith(<Routes><Route path="/workspaces/:workspaceId/packages" element={<WorkspacePackages />} /></Routes>,
                    { path: "/workspaces/ws/packages" });
}

describe("a workspace's packages", () => {
  it("upgrades a package from its row, once each decision is made", async () => {
    vi.spyOn(packagesApi, "ofWorkspace").mockResolvedValue({ workspace_id: "ws", history: [], packages: [
      row("core-objects", { upgrade_available: true, shipped_version: "2.1.0" }), row("it")] });
    vi.spyOn(packagesApi, "list").mockResolvedValue([info("core-objects"), info("it")]);
    const preview = vi.spyOn(packagesApi, "preview").mockResolvedValue(plan("upgrade", "2.0.0", "2.1.0"));
    const install = vi.spyOn(packagesApi, "install").mockResolvedValue(plan("upgrade", "2.0.0", "2.1.0"));
    page();

    fireEvent.click(await screen.findByRole("button", { name: "Upgrade to 2.1.0" }));
    await waitFor(() => expect(preview).toHaveBeenCalledWith("ws", { packages: ["core-objects"], decisions: {} }));
    expect(await screen.findByText(/Upgrade core-objects from 2.0.0 to 2.1.0/)).toBeInTheDocument();
    const go = screen.getByRole("button", { name: "Upgrade" });
    expect(go).toBeDisabled();
    fireEvent.click(screen.getByLabelText("keep this workspace's"));
    expect(go).toBeEnabled();
    fireEvent.click(go);
    await waitFor(() => expect(install).toHaveBeenCalledWith("ws", {
      packages: ["core-objects"], decisions: { [change.id]: "keep" } }));
  });

  it("goes back to a version the workspace had", async () => {
    vi.spyOn(packagesApi, "ofWorkspace").mockResolvedValue({ workspace_id: "ws", history: [], packages: [
      row("core-objects", { version: "2.1.0", shipped_version: "2.1.0",
                            revert_to: [{ version: "2.0.0", checksum: "old" }] })] });
    vi.spyOn(packagesApi, "list").mockResolvedValue([info("core-objects")]);
    const preview = vi.spyOn(packagesApi, "previewRevert").mockResolvedValue(plan("revert", "2.1.0", "2.0.0"));
    const revert = vi.spyOn(packagesApi, "revert").mockResolvedValue(plan("revert", "2.1.0", "2.0.0"));
    page();

    fireEvent.change(await screen.findByLabelText("Go back: core-objects"), { target: { value: "old" } });
    await waitFor(() => expect(preview).toHaveBeenCalledWith("ws", { package_id: "core-objects", checksum: "old", decisions: {} }));
    expect(await screen.findByText(/Go back: core-objects from 2.1.0 to 2.0.0/)).toBeInTheDocument();
    fireEvent.click(screen.getByLabelText("apply"));
    fireEvent.click(screen.getByRole("button", { name: "Go back" }));
    await waitFor(() => expect(revert).toHaveBeenCalledWith("ws", {
      package_id: "core-objects", checksum: "old", decisions: { [change.id]: "apply" } }));
  });

  it("offers the packages it does not have as cards, each previewed", async () => {
    vi.spyOn(packagesApi, "ofWorkspace").mockResolvedValue({ workspace_id: "ws", history: [], packages: [row("it")] });
    vi.spyOn(packagesApi, "list").mockResolvedValue([info("it"), info("hvac", { depends: { "core-objects": ">=2" } })]);
    const preview = vi.spyOn(packagesApi, "preview").mockResolvedValue({ ...plan("install", "", "1.0.0"),
      steps: [{ package_id: "hvac", version: "1.0.0", checksum: "z", action: "install", from_version: null,
                requested: true, result: { created: ["Chiller"] } }] });
    page();

    const add = await screen.findByRole("region", { name: "Add a package" });
    expect(within(add).queryByText("it")).not.toBeInTheDocument();            // has it already
    expect(within(add).getByText("Needs core-objects")).toBeInTheDocument();
    fireEvent.click(within(add).getByRole("button", { name: "Preview" }));
    await waitFor(() => expect(preview).toHaveBeenCalledWith("ws", { packages: ["hvac"], decisions: {} }));
    expect(await screen.findByText(/creates 1 types/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Install" })).toBeEnabled();
  });
});

describe("administration: every workspace's packages", () => {
  it("previews an upgrade everywhere and applies it where no decision is needed", async () => {
    vi.spyOn(packagesApi, "everywhere").mockResolvedValue({
      packages: [{ id: "core-objects", name: "Core objects", version: "2.1.0", behind: ["cat", "it"] },
                 { id: "it", name: "IT", version: "1.1.0", behind: [] }],
      workspaces: [{ id: "cat", name: "Catalogue", packages: [row("core-objects", { upgrade_available: true, shipped_version: "2.1.0" })] },
                   { id: "it", name: "IT", packages: [row("core-objects", { upgrade_available: true, shipped_version: "2.1.0" })] }],
    });
    const result = (status: "ready" | "upgraded") => ({ package_id: "core-objects", version: "2.1.0", workspaces: [
      { workspace_id: "cat", from_version: "2.0.0", to_version: "2.1.0", status },
      { workspace_id: "it", from_version: "2.0.0", to_version: "2.1.0", status: "needs_decisions" as const, decisions: 3 }] });
    vi.spyOn(packagesApi, "previewEverywhere").mockResolvedValue(result("ready"));
    const apply = vi.spyOn(packagesApi, "upgradeEverywhere").mockResolvedValue(result("upgraded"));
    vi.spyOn(packagesApi, "ofWorkspace").mockResolvedValue({ workspace_id: "it", history: [], packages: [
      row("core-objects", { upgrade_available: true, shipped_version: "2.1.0" })] });
    vi.spyOn(packagesApi, "list").mockResolvedValue([]);
    renderWith(<AdminPackagesPage />);

    expect(await screen.findByText("Behind in 2 workspaces: cat, it")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Preview upgrade everywhere" }));
    expect(await screen.findByText(/needs decisions — upgrade it on its own \(3\)/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Upgrade 1 workspace" }));
    await waitFor(() => expect(apply).toHaveBeenCalledWith("core-objects"));
    expect(await screen.findByText("upgraded")).toBeInTheDocument();

    // A workspace that needs decisions opens in place, with its own upgrade button.
    fireEvent.click(screen.getAllByRole("button", { name: "it" })[0]);
    expect(await screen.findByRole("button", { name: "Upgrade to 2.1.0" })).toBeInTheDocument();
  });
});
