// One stroke icon set for the whole app: 16px grid, 1.5px strokes, currentColor.
const PATHS = {
  repositories: (
    <>
      <path d="M3 3.5A1.5 1.5 0 0 1 4.5 2H13v9.5H4.5A1.5 1.5 0 0 0 3 13" />
      <path d="M3 13a1.5 1.5 0 0 0 1.5 1.5H13v-3" />
      <path d="M6 5h4" />
    </>
  ),
  meetings: (
    <>
      <rect x="2.25" y="3.25" width="11.5" height="10.5" rx="2" />
      <path d="M2.25 6.75h11.5M5.5 1.75v3M10.5 1.75v3" />
    </>
  ),
  ideas: (
    <>
      <path d="M8 1.75a4.25 4.25 0 0 0-2.5 7.7v1.3h5v-1.3A4.25 4.25 0 0 0 8 1.75Z" />
      <path d="M6.25 13.25h3.5" />
    </>
  ),
  bottlenecks: <path d="M2.5 13.25h11M4.5 13.25V8.5M8 13.25V3.5M11.5 13.25V10" />,
  settings: (
    <>
      <circle cx="8" cy="8" r="2" />
      <path d="M8 1.75v1.5M8 12.75v1.5M14.25 8h-1.5M3.25 8h-1.5M12.42 3.58l-1.06 1.06M4.64 11.36l-1.06 1.06M12.42 12.42l-1.06-1.06M4.64 4.64 3.58 3.58" />
    </>
  ),
  signout: (
    <>
      <path d="M6 2.75H4A1.25 1.25 0 0 0 2.75 4v8A1.25 1.25 0 0 0 4 13.25h2" />
      <path d="M10.5 11 13.5 8l-3-3M13.25 8H6.5" />
    </>
  ),
  chevronDown: <path d="m4.5 6.25 3.5 3.5 3.5-3.5" />,
  chevronRight: <path d="m6.25 4.5 3.5 3.5-3.5 3.5" />,
  arrowLeft: <path d="M12.5 8h-9M7 4.5 3.5 8 7 11.5" />,
  arrowRight: <path d="M3.5 8h9M9 4.5l3.5 3.5L9 11.5" />,
  close: <path d="m4 4 8 8M12 4l-8 8" />,
  check: <path d="m3.5 8.5 3 3 6-7" />,
  trash: (
    <>
      <path d="M5.75 2.25h4.5M2.75 4.25h10.5M6.5 7v4.5M9.5 7v4.5" />
      <path d="m4.25 4.25.55 8.3a1.25 1.25 0 0 0 1.25 1.2h3.9a1.25 1.25 0 0 0 1.25-1.2l.55-8.3" />
    </>
  ),
  upload: (
    <>
      <path d="M8 10.5V2.75M5 5.5l3-3 3 3" />
      <path d="M2.75 10.5v1.75A1.5 1.5 0 0 0 4.25 13.75h7.5a1.5 1.5 0 0 0 1.5-1.5V10.5" />
    </>
  ),
  external: (
    <>
      <path d="M9.5 2.75h3.75V6.5M13.25 2.75 7.5 8.5" />
      <path d="M11.5 9.5v2.75a1 1 0 0 1-1 1h-6.75a1 1 0 0 1-1-1V5.5a1 1 0 0 1 1-1H6.5" />
    </>
  ),
  refresh: (
    <>
      <path d="M13.25 8A5.25 5.25 0 1 1 11.6 4.17" />
      <path d="M13.25 2.75v3h-3" />
    </>
  ),
  layers: (
    <>
      <path d="m8 2 6 3.25L8 8.5 2 5.25 8 2Z" />
      <path d="m2 8 6 3.25L14 8M2 10.75 8 14l6-3.25" />
    </>
  ),
  shield: (
    <>
      <path d="M8 1.75 13 3.5v4.25c0 3-2.1 5.4-5 6.5-2.9-1.1-5-3.5-5-6.5V3.5L8 1.75Z" />
      <path d="m5.75 8 1.6 1.6 2.9-3.1" />
    </>
  ),
  spark: <path d="M8 1.75v3M8 11.25v3M1.75 8h3M11.25 8h3M3.6 3.6l2.1 2.1M10.3 10.3l2.1 2.1M3.6 12.4l2.1-2.1M10.3 5.7l2.1-2.1" />,
  file: (
    <>
      <path d="M9.25 1.75H4.5A1.25 1.25 0 0 0 3.25 3v10a1.25 1.25 0 0 0 1.25 1.25h7A1.25 1.25 0 0 0 12.75 13V5.25L9.25 1.75Z" />
      <path d="M9.25 1.75v3.5h3.5" />
    </>
  ),
  terminal: (
    <>
      <rect x="1.75" y="2.75" width="12.5" height="10.5" rx="2" />
      <path d="m4.75 6.25 2 1.75-2 1.75M8.5 10h2.75" />
    </>
  ),
  users: (
    <>
      <circle cx="6" cy="5.5" r="2.25" />
      <path d="M1.75 13.25c.4-2.2 2.1-3.5 4.25-3.5s3.85 1.3 4.25 3.5" />
      <path d="M10.5 3.5a2.1 2.1 0 0 1 0 4.1M12 9.9c1.2.5 2 1.6 2.25 3.35" />
    </>
  ),
};

export default function Icon({ name, size = 16, className = "", title }) {
  return (
    <svg
      className={`icon ${className}`}
      width={size}
      height={size}
      viewBox="0 0 16 16"
      aria-hidden={title ? undefined : "true"}
      role={title ? "img" : undefined}
    >
      {title && <title>{title}</title>}
      {PATHS[name]}
    </svg>
  );
}

export function Logo({ size = 28 }) {
  return (
    <svg className="logo" width={size} height={size} viewBox="0 0 32 32" aria-hidden="true">
      <rect width="32" height="32" rx="8" className="logo-bg" />
      <path d="M11 9.5v10.25A2.75 2.75 0 0 0 13.75 22.5H15" className="logo-glyph" />
      <path d="M7.5 13h8" className="logo-glyph" />
      <path d="m17.5 18.25 2.75 2.75 5-6" className="logo-tick" />
    </svg>
  );
}

export function Avatar({ name, src, size = 28 }) {
  const initials = (name || "?")
    .split(/[\s@._-]+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0].toUpperCase())
    .join("");
  if (src) return <img className="avatar" src={src} alt="" width={size} height={size} />;
  return (
    <span className="avatar avatar-fallback" style={{ width: size, height: size }} aria-hidden="true">
      {initials}
    </span>
  );
}
