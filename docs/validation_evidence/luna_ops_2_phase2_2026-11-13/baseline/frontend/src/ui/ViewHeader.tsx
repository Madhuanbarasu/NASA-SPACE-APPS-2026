import type { ReactNode } from "react";

// LUNA-OPS 2.0 view header: eyebrow label, the view's single h1, an optional subtitle and actions. Keeps the 1.0
// classes (.site-header, .site-title, .site-coords) that tests and audits address.
interface ViewHeaderProps {
  eyebrow: string;
  title: ReactNode;
  subtitle?: ReactNode;
  actions?: ReactNode;
}

export function ViewHeader({ eyebrow, title, subtitle, actions }: ViewHeaderProps) {
  return (
    <div className="site-header view-header">
      <div className="view-header-text">
        <p className="eyebrow">{eyebrow}</p>
        <h1 className="site-title">{title}</h1>
        {subtitle != null && <div className="site-coords">{subtitle}</div>}
      </div>
      {actions && <div className="view-header-actions">{actions}</div>}
    </div>
  );
}
