import { useState, type CSSProperties, type ReactNode } from "react";
import { S } from "../i18n";
import { useMediaQuery } from "../lib/useMediaQuery";

// LUNA-OPS 2.0 Phase 2: the legend card of the explorer stage (globe, map, local terrain). A disclosure (<details>), open
// by default on wide screens and closed on phones, where it would cover the view. Swatches are decorative: every entry
// says in words what its symbol means.

export type Swatch = "dot" | "ring" | "pin" | "line" | "hatch";
export interface LegendItem { swatch: Swatch; color?: string; text: string }

interface StageLegendProps {
  items: LegendItem[];
  /** extra content under the entries (display toggles, a colour bar) */
  children?: ReactNode;
  className?: string;
  /** start open (on wide screens only); the globe starts closed so the card never covers the disc */
  defaultOpen?: boolean;
}

export function StageLegend({ items, children, className, defaultOpen = true }: StageLegendProps) {
  const wide = useMediaQuery("(min-width: 901px)");
  const [open, setOpen] = useState(wide && defaultOpen);
  return (
    <details className={className ? `stage-legend ${className}` : "stage-legend"} open={open}
             onToggle={(e) => setOpen((e.currentTarget as HTMLDetailsElement).open)}>
      <summary>{S.stage.legend}</summary>
      <ul>
        {items.map((it) => (
          <li key={it.text}>
            <span className={`swatch swatch-${it.swatch}`} aria-hidden
                  style={it.color ? ({ "--swatch": it.color } as CSSProperties) : undefined} />
            <span>{it.text}</span>
          </li>
        ))}
      </ul>
      {children}
    </details>
  );
}
