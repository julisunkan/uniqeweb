---
name: Color Theme Palette
description: The active color scheme — green/red/blue/amber/brown earthy palette. Dark theme uses warm brown backgrounds, not pitch-black.
---

## Palette
- **Primary (green):** `#2e7d4f` hover `#235e3c`, light `rgba(46,125,79,0.15)`
- **Danger/secondary (red):** `#c0392b`
- **Info/accent (blue):** `#2471a3`
- **Warning (amber):** `#c9920a`
- **Brown surfaces:** `#795548` / `#6d4c41`

## Dark Theme Surfaces
- Body bg: `#1c1410` (warm brown, not black)
- Card bg: `#2e2018`
- Card hover: `#3a2820`
- Border: `#4a3428`
- Text: `#f0e0c8` (warm cream — very readable)
- Text muted: `#b89878`
- Sidebar bg: `#0f2318` (deep forest green — same in both themes)

## Light Theme Surfaces
- Body bg: `#fdf6ed` (warm cream)
- Card bg: `#ffffff`
- Border: `#d4b896`
- Text: `#3d2b1f`
- Text muted: `#8d6e63`
- Sidebar bg: `#0f2318` (same deep forest green)

## Light Theme Contrast Overrides
Badges and alerts need darker text in light mode. CSS selectors like `[data-theme="light"] .alert-success` set dark versions: success→`#1a5c30`, warning→`#7d5a00`, danger→`#7b1a13`, info→`#0e3d6e`.

**Why:** Bootstrap's badge/alert tints are pale; the default light-on-pale-tint used for dark mode fails WCAG contrast in light mode.
