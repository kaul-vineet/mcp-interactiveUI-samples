import { tokens } from '@fluentui/react-components';

// ── Global row hover styles ────────────────────────────────────────────────
export const GLOBAL_STYLES = `
.hs-row:hover { background: var(--colorBrandBackgroundHover); }
[data-theme="dark"] .hs-row:hover { background: var(--colorBrandBackgroundHover); }
@keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
@keyframes hsRowFlash {
  0%   { background: var(--colorPaletteGreenBackground1); }
  100% { background: transparent; }
}
@keyframes shimmer {
  0%   { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}
`;
if (typeof document !== 'undefined' && !document.getElementById('hs-row-hover-styles')) {
  const style = document.createElement('style');
  style.id = 'hs-row-hover-styles';
  style.textContent = GLOBAL_STYLES;
  document.head.appendChild(style);
}

// ── Fluent v9 token shim ────────────────────────────────────────────────────
// FluentProvider drives light/dark via the host's theme context. `hs(theme)`
// is kept as a thin alias mapping into Fluent tokens so existing call sites
// keep working with zero edits. Tokens auto-swap on theme change.
export function hs(_theme: 'light' | 'dark') {
  return {
    brand:      tokens.colorBrandBackground,
    brandHover: tokens.colorBrandBackgroundHover,
    accent:     tokens.colorBrandForegroundLink,
    background: tokens.colorNeutralBackground2,
    surface:    tokens.colorNeutralBackground1,
    text:       tokens.colorNeutralForeground1,
    textWeak:   tokens.colorNeutralForeground3,
    border:     tokens.colorNeutralStroke2,
    headerBg:   tokens.colorNeutralBackground3,
    success:    tokens.colorPaletteGreenForeground1,
    danger:     tokens.colorPaletteRedForeground1,
    warn:       tokens.colorPaletteDarkOrangeForeground1,
    expandedBg: tokens.colorSubtleBackgroundSelected,
  };
}

export function timeAgo(iso: string): string {
  const secs = Math.floor((Date.now() - new Date(iso).getTime()) / 1000);
  if (secs < 5) return 'just now';
  if (secs < 60) return `${secs}s ago`;
  if (secs < 3600) return `${Math.floor(secs / 60)}m ago`;
  return `${Math.floor(secs / 3600)}h ago`;
}
