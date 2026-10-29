import { useId } from "react";
import type { CompanionProposal } from "../api/client";

export interface PortDraft { on: boolean; port_label: string; port_kind: string; mac: string; fromAssistant: boolean }
export interface AddressDraft { on: boolean; ip: string; hostname: string; fromAssistant: boolean }

export const emptyPort: PortDraft = { on: false, port_label: "eth0", port_kind: "RJ45", mac: "", fromAssistant: false };
export const emptyAddress: AddressDraft = { on: false, ip: "", hostname: "", fromAssistant: false };

const MAC = /^([0-9a-f]{2}[:-]){5}[0-9a-f]{2}$|^[0-9a-f]{4}\.[0-9a-f]{4}\.[0-9a-f]{4}$|^[0-9a-f]{12}$/i;
export const macLooksRight = (v: string) => !v.trim() || MAC.test(v.trim());

/** What the assistant proposed, as the form's drafts (ticked when it read them). */
export function fromProposals(list: CompanionProposal[] | undefined, port: PortDraft, address: AddressDraft) {
  // The network port is the one with the MAC; a port table's other ports are listed apart (ProposedPorts).
  const p = list?.find((c) => c.kind === "port" && !!c.attributes.mac);
  const a = list?.find((c) => c.kind === "address");
  return {
    port: p ? { on: p.selected, port_label: p.attributes.port_label ?? "eth0", port_kind: p.attributes.port_kind ?? "RJ45",
                mac: p.attributes.mac ?? "", fromAssistant: true } : port,
    address: a ? { on: a.selected, ip: a.attributes.ip ?? "", hostname: a.attributes.hostname ?? "", fromAssistant: true } : address,
  };
}

/** The new record's network port (its MAC lives there, not on the record) and, optionally, its registered address:
 *  made together with it, linked to it. Shown when the assistant read a MAC or an address, or when the type is
 *  equipment that is on a network. */
export function NetworkPortSection({ port, setPort, address, setAddress, addressAvailable }: {
  port: PortDraft; setPort: (p: PortDraft) => void;
  address: AddressDraft; setAddress: (a: AddressDraft) => void;
  addressAvailable: boolean;
}) {
  const id = useId();
  const badMac = !macLooksRight(port.mac);
  return (
    <fieldset className="rounded-md border border-slate-200 bg-white p-3">
      <legend className="px-1 text-sm font-medium text-slate-800">Network</legend>
      <label className="flex items-start gap-2 text-sm">
        <input type="checkbox" className="mt-0.5" checked={port.on} onChange={(e) => setPort({ ...port, on: e.target.checked })} />
        <span>
          Add its network port
          <span className="block text-xs text-slate-500">
            {port.fromAssistant ? "Proposed: a MAC address was read. " : ""}
            A separate Equipment Port record, “port of” this one: the MAC identifies the port, and cables and switch ports
            connect to it.
          </span>
        </span>
      </label>
      {port.on && (
        <div className="mt-2 grid gap-2 sm:grid-cols-3">
          <label className="text-xs text-slate-600" htmlFor={`${id}-mac`}>MAC address
            <input id={`${id}-mac`} value={port.mac} onChange={(e) => setPort({ ...port, mac: e.target.value })}
                   placeholder="00:30:53:37:86:28" aria-invalid={badMac}
                   className={`mt-0.5 w-full rounded border px-2 py-1 font-mono text-sm ${badMac ? "border-rose-400" : "border-slate-300"}`} />
            {badMac && <span className="text-rose-700">Not a MAC address (aa:bb:cc:dd:ee:ff)</span>}
          </label>
          <label className="text-xs text-slate-600" htmlFor={`${id}-label`}>Port label
            <input id={`${id}-label`} value={port.port_label} onChange={(e) => setPort({ ...port, port_label: e.target.value })}
                   className="mt-0.5 w-full rounded border border-slate-300 px-2 py-1 text-sm" />
          </label>
          <label className="text-xs text-slate-600" htmlFor={`${id}-kind`}>Kind
            <select id={`${id}-kind`} value={port.port_kind} onChange={(e) => setPort({ ...port, port_kind: e.target.value })}
                    className="mt-0.5 w-full rounded border border-slate-300 px-2 py-1 text-sm">
              {["RJ45", "SFP", "EtherCAT", "USB", "Other"].map((k) => <option key={k}>{k}</option>)}
            </select>
          </label>
        </div>
      )}
      {addressAvailable && (
        <>
          <label className="mt-3 flex items-start gap-2 text-sm">
            <input type="checkbox" className="mt-0.5" checked={address.on} onChange={(e) => setAddress({ ...address, on: e.target.checked })} />
            <span>
              Add its network address
              <span className="block text-xs text-slate-500">
                {address.fromAssistant ? "Proposed: an address was read. " : ""}An Address Record (IP, hostname) this one is “described by”.
              </span>
            </span>
          </label>
          {address.on && (
            <div className="mt-2 grid gap-2 sm:grid-cols-2">
              <label className="text-xs text-slate-600" htmlFor={`${id}-ip`}>IP address
                <input id={`${id}-ip`} value={address.ip} onChange={(e) => setAddress({ ...address, ip: e.target.value })}
                       className="mt-0.5 w-full rounded border border-slate-300 px-2 py-1 font-mono text-sm" />
              </label>
              <label className="text-xs text-slate-600" htmlFor={`${id}-host`}>Hostname
                <input id={`${id}-host`} value={address.hostname} onChange={(e) => setAddress({ ...address, hostname: e.target.value })}
                       className="mt-0.5 w-full rounded border border-slate-300 px-2 py-1 font-mono text-sm" />
              </label>
            </div>
          )}
        </>
      )}
    </fieldset>
  );
}
