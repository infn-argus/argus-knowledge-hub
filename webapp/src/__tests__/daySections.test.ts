import { fireEvent, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createElement } from "react";
import { describe, expect, it } from "vitest";
import { DocumentReshape } from "../pages/documents/Reshape";
import { renderWith } from "../test/render";
import { dayOf, daySections } from "../lib/daySections";

const LOG = `SPARC Running LOG
October 2026

Istruzioni per l'uso:
- Nuove entries in alto!

26.10.2026

Abbiamo creato una cartella.

## 16.10.2026

09h10: laser acceso.
01.10.2026 11h37: a time on a day's line is an entry, not a day

Lunedì 1 ottobre 2026

11h37: laser ottimizzato con compressore a -1300.`;

describe("the days of a running log", () => {
  it("reads a line that is a date and nothing else", () => {
    expect(dayOf("26.10.2026")).toBe("2026-10-26");
    expect(dayOf("## 16/10/26")).toBe("2026-10-16");
    expect(dayOf("2026-10-03")).toBe("2026-10-03");
    expect(dayOf("Lunedì 1 ottobre 2026")).toBe("2026-10-01");
    expect(dayOf("**October 5, 2026**")).toBe("2026-10-05");
    expect(dayOf("01.10.2026 11h37: laser")).toBeNull();
    expect(dayOf("31.02.2026")).toBeNull();
    expect(dayOf("Port 4 57600")).toBeNull();
  });

  it("splits the log into its days, in the order written, without the preamble", () => {
    const days = daySections(LOG);
    expect(days.map((d) => d.date)).toEqual(["2026-10-26", "2026-10-16", "2026-10-01"]);
    expect(days[0].text).toBe("26.10.2026\n\nAbbiamo creato una cartella.");
    expect(days[1].label).toBe("16.10.2026");
    expect(days[1].text).toContain("a time on a day's line is an entry");
    expect(days.some((d) => d.text.includes("Istruzioni"))).toBe(false);
  });

  it("finds no days in a text of one day", () => {
    expect(daySections("26.10.2026\n\nOne day only.")).toEqual([]);
    expect(daySections("Notes without dates.")).toEqual([]);
  });
});


describe("reworking a running log", () => {
  it("offers its days and puts one day, with its date, in the box", async () => {
    renderWith(createElement(DocumentReshape), { path: "/documents/reshape", cache: { '["schemas"]': [] } });
    const box = screen.getByPlaceholderText(/Paste the notes/) as HTMLTextAreaElement;
    fireEvent.change(box, { target: { value: LOG } });
    expect(screen.getByText(/This text holds 3 days/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /16\.10\.2026/ }));
    expect(box.value.startsWith("## 16.10.2026")).toBe(true);
    expect(box.value).not.toContain("Abbiamo creato");
    expect(screen.getByDisplayValue("2026-10-16")).toBeInTheDocument();           // its date, for the draft
    expect(screen.getByText(/This text holds 3 days/)).toBeInTheDocument();        // the days stay listed
    await userEvent.click(screen.getByRole("button", { name: "Back to the whole text" }));
    expect(box.value).toBe(LOG);
  });
});
