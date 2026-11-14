import { useEffect, useMemo, useRef, useState } from "react";
import type { EventItem, Result } from "../api/types";
import { S } from "../i18n";
import { fmtDuration, fmtUTC } from "../lib/format";
import { timeAxis } from "../lib/timeAxis";

// LUNA-OPS 2.0 Phase 3: the window's events in time order (the API's events: rise and set of each body and Earth-Sun
// contacts, with the API's own names), each with its time from the time cursor (a subtraction of the two served times,
// like the countdowns). Choosing an event moves the shared time cursor to the display step nearest to it.
// Keyboard: one Tab stop (the event at or after the cursor); Up/Down, Home/End move; Enter or Space chooses.

const A = S.analysis;
interface Props { result: Result; cursor: number; onCursor: (i: number) => void }

/** Text for an event's time relative to the cursor ET. */
export function relativeTo(evEt: number, curEt: number): string {
  const d = evEt - curEt;
  if (Math.abs(d) < 1) return A.relNow;
  return d > 0 ? A.relIn(fmtDuration(d / 3600)) : A.relAgo(fmtDuration(-d / 3600));
}

export function EventList({ result, cursor, onCursor }: Props) {
  const events: EventItem[] = result.events;
  const ax = useMemo(() => timeAxis(result, 0, 1), [result]);
  const curEt = result.series.et[Math.min(cursor, result.series.et.length - 1)];
  // the event at or after the cursor: the list's single Tab stop and its highlighted row
  const nextK = useMemo(() => { const k = events.findIndex((e) => e.et >= curEt - 0.5); return k < 0 ? events.length - 1 : k; }, [events, curEt]);
  const [focusK, setFocusK] = useState<number | null>(null);
  const tabK = focusK ?? nextK;
  const list = useRef<HTMLOListElement>(null);
  // keep the highlighted (next) event in view inside the list when the cursor moves, without moving the page
  useEffect(() => {
    const ol = list.current, li = ol?.children[nextK] as HTMLElement | undefined;
    if (!ol || !li || focusK != null) return;
    if (li.offsetTop < ol.scrollTop || li.offsetTop + li.offsetHeight > ol.scrollTop + ol.clientHeight) ol.scrollTop = li.offsetTop - ol.clientHeight / 3;
  }, [nextK, focusK]);
  if (!events.length) return <p className="hint event-empty">{A.noEvents}</p>;
  const choose = (k: number) => onCursor(ax.nearestIdx(events[k].et));
  const move = (k: number) => {
    const n = Math.max(0, Math.min(events.length - 1, k));
    setFocusK(n);
    (list.current?.children[n] as HTMLElement | undefined)?.focus();
  };

  return (
    <div className="event-list-wrap">
      <h3 className="event-list-head" id="event-list-title">{A.eventsHeading(events.length)}</h3>
      <ol className="event-list" role="listbox" aria-labelledby="event-list-title" ref={list}
          onBlur={(e) => { if (!e.currentTarget.contains(e.relatedTarget as Node)) setFocusK(null); }}>
        {events.map((ev, k) => (
          <li key={k} role="option" aria-selected={k === nextK} tabIndex={k === tabK ? 0 : -1}
              className={`event-row is-${ev.target}${k === nextK ? " is-next" : ""}${ev.et < curEt - 0.5 ? " is-past" : ""}`}
              onClick={() => { setFocusK(k); choose(k); }}
              onKeyDown={(e) => {
                const to = e.key === "ArrowDown" ? k + 1 : e.key === "ArrowUp" ? k - 1 : e.key === "Home" ? 0 : e.key === "End" ? events.length - 1 : null;
                if (to != null) { e.preventDefault(); move(to); return; }
                if (e.key === "Enter" || e.key === " ") { e.preventDefault(); choose(k); }
              }}>
            <span className={`event-glyph ${ev.function === "ecl_contact" ? "is-contact" : ev.direction > 0 ? "is-rise" : "is-set"}`} aria-hidden />
            <span className="event-name">{ev.name}</span>
            <span className="event-time">{fmtUTC(ev.utc, true)}</span>
            <span className="event-rel">{relativeTo(ev.et, curEt)}</span>
          </li>
        ))}
      </ol>
      <p className="hint">{A.eventListHint}</p>
    </div>
  );
}
