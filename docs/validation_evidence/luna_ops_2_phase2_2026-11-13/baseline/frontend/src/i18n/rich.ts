import { Fragment, createElement, type ReactNode } from "react";

/** The {name} placeholders of a template string, as a union of literal names (compile-time check). */
export type Placeholders<T extends string> =
  T extends `${string}{${infer K}}${infer Rest}` ? K | Placeholders<Rest> : never;

/**
 * Renders a string template whose {name} placeholders are filled with React nodes (for example a bold number), so a
 * sentence stays whole in src/i18n/en.ts instead of being cut into fragments around the markup. TypeScript requires
 * exactly the template's placeholder names; an unknown or missing value is a compile error.
 */
export function rich<T extends string>(template: T, values: { [K in Placeholders<T>]: ReactNode }): ReactNode {
  const vals = values as Record<string, ReactNode>;
  const parts = template.split(/\{(\w+)\}/);
  return createElement(Fragment, null, ...parts.map((p, i) => (i % 2 === 1 ? vals[p] : p)));
}
