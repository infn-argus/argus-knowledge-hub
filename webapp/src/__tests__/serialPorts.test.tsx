import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { intakeApi, type ProposeResult } from "../api/client";
import { portSettings } from "../components/ProposedPorts";
import { SuggestFromFile } from "../components/SuggestFromFile";
import { renderWith } from "../test/render";

const port = (n: number, extra = {}) => ({
  kind: "port" as const, type_uid: "p", relation: "port of", selected: true, confidence: 0.9, evidence: null,
  grounded: true, reason: "the input lists the unit's ports",
  attributes: { port_label: `Port ${n}`, port_kind: "RS-232", baud: 9600, framing: "8N1", flow_control: "RTS/CTS",
                tcp_port: 4000 + n, ...extra },
});

const result: ProposeResult = {
  run_id: "run-1", profile_id: null, proposed: [], unchanged: [], dropped: [],
  companions: [port(2), port(3), port(4, { port_role: "VITARA+flame", baud: 57600, flow_control: "XON/XOFF" })],
  port_changes: [{ port: { uid: "p1", key: "PORT-1", name: "moxa · Port 1", label: "Port 1" }, field: "baud",
                   value: 9600, current: 19200 }],
};

afterEach(() => vi.restoreAllMocks());

describe("a unit's ports read from a file", () => {
  it("writes a serial port's settings as a converter's page does", () => {
    expect(portSettings({ baud: 9600, framing: "7N1", flow_control: "RTS/CTS" })).toBe("9600 · 7N1 · RTS/CTS");
    expect(portSettings({ baud: 57600, framing: "8N1", flow_control: "None" })).toBe("57600 · 8N1");
  });

  it("offers the ports the unit has not, proposes changes on the ones it has, and adds the chosen", async () => {
    vi.spyOn(intakeApi, "propose").mockResolvedValue(result);
    const add = vi.spyOn(intakeApi, "addCompanions").mockResolvedValue({
      ports: [{ uid: "a", key: "PORT-3", name: "moxa · Port 3" }, { uid: "b", key: "PORT-4", name: "moxa · Port 4" }],
      addresses: [] });
    renderWith(<SuggestFromFile assetUid="moxa" />, { cache: { '["ai-status"]': { validated: true, has_vision: true } } });
    await userEvent.type(screen.getByRole("textbox"), "the serial settings page");
    await userEvent.click(screen.getByRole("button", { name: "Propose from the text" }));
    expect(await screen.findByText("VITARA+flame")).toBeInTheDocument();
    expect(screen.getByText("57600 · 8N1 · XON/XOFF")).toBeInTheDocument();
    expect(screen.getByText(/1 value\(s\) proposed on its ports/)).toBeInTheDocument();
    expect(screen.getByText("(now 19200)")).toBeInTheDocument();
    expect(screen.queryByText(/0 value\(s\) proposed\./)).toBeNull();
    await userEvent.click(screen.getByRole("checkbox", { name: "Add Port 2" }));
    await userEvent.click(screen.getByRole("button", { name: "Add 2 to this unit" }));
    expect(add).toHaveBeenCalledWith("moxa", {
      ports: [result.companions![1].attributes, result.companions![2].attributes], addresses: [], run_id: "run-1" });
    expect(await screen.findByText(/Added 2: PORT-3, PORT-4/)).toBeInTheDocument();
  });
});
