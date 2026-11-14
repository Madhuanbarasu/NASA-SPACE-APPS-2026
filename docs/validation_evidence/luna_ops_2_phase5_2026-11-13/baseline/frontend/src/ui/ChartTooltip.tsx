import type { ReactNode } from "react";

// LUNA-OPS 2.0 Phase 3: the hover panel of an analysis chart, placed beside the pointer inside the chart box and flipped
// to the other side near the right edge. Decorative for assistive technology (aria-hidden): the same values are in the
// chart's readout line, the time-cursor readout and the tables.

interface ChartTooltipProps {
  /** pointer position in px inside the chart box */
  x: number; y: number;
  /** width of the chart box in px */
  boxWidth: number;
  children: ReactNode;
}

export function ChartTooltip({ x, y, boxWidth, children }: ChartTooltipProps) {
  const right = x > boxWidth * 0.62;
  const style = right ? { right: Math.max(4, boxWidth - x + 14), top: Math.max(4, y - 10) } : { left: x + 14, top: Math.max(4, y - 10) };
  return <div className="chart-tip" style={style} aria-hidden>{children}</div>;
}
