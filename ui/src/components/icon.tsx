import type { JSX } from 'preact'

type IconName =
  | 'adjustments'
  | 'apply'
  | 'braces'
  | 'calendar'
  | 'chevron-left'
  | 'chevron-right'
  | 'chevrons-left'
  | 'chevrons-right'
  | 'circle-half'
  | 'download'
  | 'eye'
  | 'eye-off'
  | 'panel-left'
  | 'panel-right'
  | 'rotate-ccw'
  | 'trash'
  | 'x'

interface IconProps {
  name: IconName
  class?: string
}

const ICON_PATHS: Record<IconName, JSX.Element> = {
  adjustments: (
    <>
      <path d="M4 6h10" />
      <path d="M4 12h16" />
      <path d="M10 18h10" />
      <circle cx="16" cy="6" r="2" />
      <circle cx="8" cy="12" r="2" />
      <circle cx="14" cy="18" r="2" />
    </>
  ),
  apply: (
    <>
      <path d="m5 12 4 4 10-10" />
    </>
  ),
  braces: (
    <>
      <path d="M9 4c-2 0-3 1-3 3v2c0 1-1 2-2 2 1 0 2 1 2 2v2c0 2 1 3 3 3" />
      <path d="M15 4c2 0 3 1 3 3v2c0 1 1 2 2 2-1 0-2 1-2 2v2c0 2-1 3-3 3" />
    </>
  ),
  calendar: (
    <>
      <rect x="3" y="5" width="18" height="16" rx="2" />
      <path d="M16 3v4" />
      <path d="M8 3v4" />
      <path d="M3 10h18" />
    </>
  ),
  'chevron-left': <path d="m15 18-6-6 6-6" />,
  'chevron-right': <path d="m9 18 6-6-6-6" />,
  'chevrons-left': (
    <>
      <path d="m13 18-6-6 6-6" />
      <path d="m19 18-6-6 6-6" />
    </>
  ),
  'chevrons-right': (
    <>
      <path d="m5 18 6-6-6-6" />
      <path d="m11 18 6-6-6-6" />
    </>
  ),
  'circle-half': (
    <>
      <path d="M12 3a9 9 0 1 0 0 18V3Z" />
      <path d="M12 3a9 9 0 0 1 0 18" />
    </>
  ),
  download: (
    <>
      <path d="M12 4v11" />
      <path d="m7 11 5 5 5-5" />
      <path d="M4 20h16" />
    </>
  ),
  eye: (
    <>
      <path d="M2 12s4-6 10-6 10 6 10 6-4 6-10 6S2 12 2 12Z" />
      <circle cx="12" cy="12" r="3" />
    </>
  ),
  'eye-off': (
    <>
      <path d="m3 3 18 18" />
      <path d="M10.6 10.7a3 3 0 0 0 4.2 4.2" />
      <path d="M9.9 5.1A10.6 10.6 0 0 1 12 5c6 0 10 7 10 7a18.2 18.2 0 0 1-3.1 3.8" />
      <path d="M6.2 6.2A18.8 18.8 0 0 0 2 12s4 7 10 7a9.7 9.7 0 0 0 2.6-.3" />
    </>
  ),
  'panel-left': (
    <>
      <rect x="3" y="4" width="18" height="16" rx="2" />
      <path d="M9 4v16" />
    </>
  ),
  'panel-right': (
    <>
      <rect x="3" y="4" width="18" height="16" rx="2" />
      <path d="M15 4v16" />
    </>
  ),
  'rotate-ccw': (
    <>
      <path d="M3 12a9 9 0 1 0 3-6.7" />
      <path d="M3 3v6h6" />
    </>
  ),
  trash: (
    <>
      <path d="M4 7h16" />
      <path d="M9 7V4h6v3" />
      <path d="M6 7l1 13h10l1-13" />
      <path d="M10 11v6" />
      <path d="M14 11v6" />
    </>
  ),
  x: (
    <>
      <path d="m18 6-12 12" />
      <path d="m6 6 12 12" />
    </>
  ),
}

export function Icon({ name, class: className }: IconProps) {
  return (
    <svg
      class={className}
      viewBox="0 0 24 24"
      width="16"
      height="16"
      fill="none"
      stroke="currentColor"
      stroke-width="1.8"
      stroke-linecap="round"
      stroke-linejoin="round"
      aria-hidden="true"
    >
      {ICON_PATHS[name]}
    </svg>
  )
}
