import type { CSSProperties } from "react";

// LUNA-OPS 2.0 Phase 3: the inline legend of an analysis chart. Every entry says in words what its symbol means; the
// symbol itself is decorative.

export type ChartSwatch = "fill" | "line" | "dashed" | "hatch" | "outline-dashed" | "band" | "rise" | "set" | "contact" | "ring" | "cursor";
export interface ChartLegendItem { swatch: ChartSwatch; color?: string; text: string }

export function ChartLegend({ items, label, className }: { items: ChartLegendItem[]; label?: string; className?: string }) {
  return (
    <ul className={className ? `chart-legend ${className}` : "chart-legend"} aria-label={label}>
      {items.map((it) => (
        <li key={it.text}>
          <i className={`lg lg-${it.swatch}`} aria-hidden style={it.color ? ({ "--lg": it.color } as CSSProperties) : undefined} />
          {it.text}
        </li>
      ))}
    </ul>
  );
}
