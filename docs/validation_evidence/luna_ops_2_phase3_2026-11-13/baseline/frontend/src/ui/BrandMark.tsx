// LUNA-OPS 2.0 brand mark: the Moon (terminator shading) inside an orbit ring, with the Sun as a small gold point.
// Decorative: the brand name next to it is the text.
export function BrandMark() {
  return (
    <svg className="brand-logo" viewBox="0 0 32 32" aria-hidden="true" focusable="false">
      <defs>
        <radialGradient id="brand-moon" cx="38%" cy="34%" r="70%">
          <stop offset="0" stopColor="#dfe6ee" />
          <stop offset="0.55" stopColor="#8796a6" />
          <stop offset="1" stopColor="#2a3644" />
        </radialGradient>
      </defs>
      <ellipse cx="16" cy="16" rx="14.5" ry="6.2" fill="none" stroke="#4cc9d6" strokeOpacity="0.55" strokeWidth="1.2"
               transform="rotate(-24 16 16)" />
      <circle cx="16" cy="16" r="8.4" fill="url(#brand-moon)" />
      <circle cx="12.6" cy="13.4" r="1.6" fill="#5d6b7a" fillOpacity="0.55" />
      <circle cx="18.8" cy="18.6" r="1.1" fill="#5d6b7a" fillOpacity="0.5" />
      <circle cx="27" cy="9.2" r="1.9" fill="#f2b544" />
    </svg>
  );
}
