// LUNA-OPS 2.0 interface icons: small stroke icons, always decorative (the control that holds one carries the name).
const PATHS = {
  menu: "M4 7h16M4 12h16M4 17h16",
  close: "M6 6l12 12M18 6L6 18",
  sliders: "M4 7h9M17 7h3M4 17h3M11 17h9M15 5v4M9 15v4",
  chevronLeft: "M15 6l-6 6 6 6",
  // Phase 2: explorer navigation
  chevronRight: "M9 6l6 6-6 6",
  chevronUp: "M6 15l6-6 6 6",
  chevronDown: "M6 9l6 6 6-6",
  plus: "M12 5v14M5 12h14",
  minus: "M5 12h14",
  reset: "M4 11.5L12 4.5l8 7M6.5 10v9.5h11V10",
  target: "M4 12a8 8 0 1 0 16 0a8 8 0 1 0-16 0M9.5 12a2.5 2.5 0 1 0 5 0a2.5 2.5 0 1 0-5 0",
  crosshair: "M12 3v6M12 15v6M3 12h6M15 12h6",
  rotateLeft: "M4 5v5h5M5.2 14.5A7.5 7.5 0 1 0 6 8.2L4 10",
  rotateRight: "M20 5v5h-5M18.8 14.5A7.5 7.5 0 1 1 18 8.2l2 1.8",
  fit: "M4 9V4h5M15 4h5v5M20 15v5h-5M9 20H4v-5",
  // Phase 4: mission dashboard quick actions
  globe: "M3.5 12a8.5 8.5 0 1 0 17 0a8.5 8.5 0 1 0-17 0M3.5 12h17M12 3.5c2.6 2.4 2.6 14.6 0 17M12 3.5c-2.6 2.4-2.6 14.6 0 17",
  map: "M4 6.5l5-2 6 2 5-2v13l-5 2-6-2-5 2zM9 4.5v13M15 6.5v13",
  terrain: "M3 19l6-9 4 5 3-4 5 8z",
  chart: "M4 19V5M4 19h16M8 15l3-4 3 2 5-6",
  compare: "M5 20V9M10 20V4M15 20v-7M20 20v-11",
} as const;

export type IconName = keyof typeof PATHS;

export function Icon({ name }: { name: IconName }) {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false" fill="none" stroke="currentColor" strokeWidth={1.8}
         strokeLinecap="round" strokeLinejoin="round">
      <path d={PATHS[name]} />
    </svg>
  );
}
