import { timeFormatLocale, type TimeLocaleDefinition } from "d3";
import { en } from "./en";

/** The interface strings (English). Read text as S.section.key; see src/i18n/en.ts for the conventions. */
export const S = en;
export type { Strings } from "./en";
export { rich } from "./rich";

const L = en.format.timeLocale;
type Days = TimeLocaleDefinition["days"];
type Months = TimeLocaleDefinition["months"];

/** d3 time locale built from the strings, so chart axis dates use the same month and day names. */
export const timeLocale = timeFormatLocale({
  dateTime: L.dateTime, date: L.date, time: L.time,
  periods: [L.periods[0], L.periods[1]],
  days: [...L.days] as unknown as Days, shortDays: [...L.shortDays] as unknown as Days,
  months: [...L.months] as unknown as Months, shortMonths: [...L.shortMonths] as unknown as Months,
});
