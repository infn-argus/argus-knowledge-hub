import { screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { emptyAddress, emptyPort, fromProposals, macLooksRight, NetworkPortSection } from "../components/NetworkPortSection";
import { renderWith } from "../test/render";

describe("a new record's network port", () => {
  it("takes the assistant's MAC and address, ticked", () => {
    const { port, address } = fromProposals([
      { kind: "port", type_uid: "p", relation: "port of", selected: true, confidence: 0.95, evidence: "MAC: 00:30:53:37:86:28",
        grounded: true, reason: "", attributes: { port_label: "eth0", port_kind: "RJ45", mac: "00:30:53:37:86:28" } },
      { kind: "address", type_uid: "a", relation: "described by", selected: true, confidence: 0.9, evidence: "10.0.0.5",
        grounded: true, reason: "", attributes: { ip: "10.0.0.5" } },
    ], emptyPort, emptyAddress);
    expect(port).toMatchObject({ on: true, mac: "00:30:53:37:86:28", fromAssistant: true });
    expect(address).toMatchObject({ on: true, ip: "10.0.0.5" });
  });

  it("is offered unticked when nothing was read", () => {
    renderWith(<NetworkPortSection port={emptyPort} setPort={vi.fn()} address={emptyAddress} setAddress={vi.fn()} addressAvailable />);
    expect(screen.getByRole("checkbox", { name: /Add its network port/ })).not.toBeChecked();
    expect(screen.queryByLabelText("MAC address")).toBeNull();
  });

  it("says when a MAC is malformed", () => {
    renderWith(<NetworkPortSection port={{ ...emptyPort, on: true, mac: "00:30:53" }} setPort={vi.fn()}
                                   address={emptyAddress} setAddress={vi.fn()} addressAvailable={false} />);
    expect(screen.getByLabelText(/MAC address/)).toHaveAttribute("aria-invalid", "true");
    expect(screen.queryByRole("checkbox", { name: /network address/ })).toBeNull();
    expect(macLooksRight("00-30-53-37-86-28")).toBe(true);
    expect(macLooksRight("0030.5337.8628")).toBe(true);
  });
});
