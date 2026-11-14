import type { ReactNode } from "react";

// LUNA-OPS 2.0 Phase 3: the header of an analysis workspace section (eyebrow, h2, optional data-class tag and actions).

interface SectionHeaderProps {
  id: string;
  eyebrow?: string;
  title: string;
  /** a data-class tag (Calculated, Measured input, Illustrative) or a validation status */
  tag?: ReactNode;
  actions?: ReactNode;
}

export function SectionHeader({ id, eyebrow, title, tag, actions }: SectionHeaderProps) {
  return (
    <div className="section-head">
      <div className="section-head-text">
        {eyebrow && <p className="eyebrow">{eyebrow}</p>}
        <h2 id={id}>{title}{tag && <> {tag}</>}</h2>
      </div>
      {actions && <div className="section-head-actions">{actions}</div>}
    </div>
  );
}
