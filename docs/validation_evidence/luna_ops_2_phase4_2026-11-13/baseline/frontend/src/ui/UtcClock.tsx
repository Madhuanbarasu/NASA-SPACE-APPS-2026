import { useEffect, useState } from "react";
import { S } from "../i18n";

// LUNA-OPS 2.0 command-bar clock: the current UTC time (all LUNA-OPS times are UTC). Decorative chrome, so it is hidden
// from assistive technology instead of being announced every second; only this component re-renders each second.
export function UtcClock() {
  const [now, setNow] = useState(() => new Date());
  useEffect(() => {
    const t = window.setInterval(() => setNow(new Date()), 1000);
    return () => window.clearInterval(t);
  }, []);
  const iso = now.toISOString();
  return (
    <span className="utc-clock" aria-hidden="true">
      <b>{S.shell.clockUnit}</b>{S.shell.clock(iso.slice(0, 10), iso.slice(11, 19))}
    </span>
  );
}
