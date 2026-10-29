/** The days a running log holds: each line that is a date alone (26.10.2026, 2026-10-26, "Lunedì 26 ottobre
 *  2026", "October 26, 2026", as a heading or not) starts a day, which runs to the next such line. A log has
 *  its newest day first or last; the order is kept as written. What comes before the first day (a title,
 *  instructions) belongs to no day and is left out of each. */

export interface DaySection {
  /** The heading as written. */
  label: string;
  /** The day, as YYYY-MM-DD. */
  date: string;
  /** The day's text, its heading first. */
  text: string;
}

const MONTHS: Record<string, number> = {
  gennaio: 1, febbraio: 2, marzo: 3, aprile: 4, maggio: 5, giugno: 6, luglio: 7, agosto: 8, settembre: 9,
  ottobre: 10, novembre: 11, dicembre: 12,
  january: 1, february: 2, march: 3, april: 4, may: 5, june: 6, july: 7, august: 8, september: 9,
  october: 10, november: 11, december: 12,
  gen: 1, feb: 2, mar: 3, apr: 4, mag: 5, giu: 6, lug: 7, ago: 8, set: 9, ott: 10, nov: 11, dic: 12,
  jan: 1, jun: 6, jul: 7, aug: 8, sep: 9, sept: 9, oct: 10, dec: 12,
};
const WEEKDAY = "(?:luned[iì]|marted[iì]|mercoled[iì]|gioved[iì]|venerd[iì]|sabato|domenica|lun|mar|mer|gio|ven|sab|dom|" +
  "monday|tuesday|wednesday|thursday|friday|saturday|sunday|mon|tue|wed|thu|fri|sat|sun)\\.?,?\\s+";
const MONTH = "([a-zàèéìòù]{3,9})\\.?";
const PATTERNS: [RegExp, (m: RegExpMatchArray) => [number, number, number] | null][] = [
  [/^(\d{4})-(\d{1,2})-(\d{1,2})$/, (m) => [+m[1], +m[2], +m[3]]],
  [/^(\d{1,2})[./-](\d{1,2})[./-](\d{4}|\d{2})$/, (m) => [year(m[3]), +m[2], +m[1]]],
  [new RegExp(`^(\\d{1,2})\\s+${MONTH}\\s+(\\d{4})$`, "i"),
   (m) => (MONTHS[m[2].toLowerCase()] ? [+m[3], MONTHS[m[2].toLowerCase()], +m[1]] : null)],
  [new RegExp(`^${MONTH}\\s+(\\d{1,2}),?\\s+(\\d{4})$`, "i"),
   (m) => (MONTHS[m[1].toLowerCase()] ? [+m[3], MONTHS[m[1].toLowerCase()], +m[2]] : null)],
];

function year(y: string): number {
  return y.length === 2 ? 2000 + +y : +y;
}

/** The day a line names, when the line is a date and nothing else (YYYY-MM-DD), or null. */
export function dayOf(line: string): string | null {
  let s = line.trim().replace(/^#{1,6}\s*/, "").replace(/^\*\*(.*)\*\*$/, "$1").replace(/[:.]$/, "").trim();
  if (!s || s.length > 40) return null;
  s = s.replace(new RegExp(`^${WEEKDAY}`, "i"), "");
  for (const [re, parts] of PATTERNS) {
    const m = s.match(re);
    const ymd = m && parts(m);
    if (!ymd) continue;
    const [y, mo, d] = ymd;
    const when = new Date(Date.UTC(y, mo - 1, d));
    if (when.getUTCFullYear() !== y || when.getUTCMonth() !== mo - 1 || when.getUTCDate() !== d) return null;
    return `${y}-${String(mo).padStart(2, "0")}-${String(d).padStart(2, "0")}`;
  }
  return null;
}

/** The days in the text, or none when it holds fewer than two (one day is just the text). */
export function daySections(text: string): DaySection[] {
  const lines = text.split("\n");
  const starts: { at: number; date: string; label: string }[] = [];
  lines.forEach((line, at) => {
    const date = dayOf(line);
    if (date) starts.push({ at, date, label: line.trim().replace(/^#{1,6}\s*/, "") });
  });
  if (starts.length < 2) return [];
  return starts.map((s, i) => ({
    label: s.label,
    date: s.date,
    text: lines.slice(s.at, i + 1 < starts.length ? starts[i + 1].at : lines.length).join("\n").trim(),
  }));
}
