---
name: Theme FOUC Fix
description: How the dark/light theme flash-of-white is prevented. Inline head script + Bootstrap CSS variable overrides.
---

## Problem
Bootstrap 5 defaults to `--bs-body-bg: white`. When the page renders, Bootstrap's white shows briefly before our CSS variables kick in from `[data-theme]`. Also, if localStorage has 'light' saved, the JS IIFE at bottom of page switches theme visibly after render.

## Fix
1. **Inline `<script>` in `<head>`** (first element, before any CSS link): reads `localStorage.getItem('theme')` and immediately calls `document.documentElement.setAttribute('data-theme', t)`. This runs before any CSS is parsed.
2. **Bootstrap CSS variable overrides** in both `[data-theme="dark"]` and `[data-theme="light"]` blocks: `--bs-body-bg`, `--bs-body-color`, `--bs-card-bg`, `--bs-border-color`, `--bs-modal-bg`, etc.
3. **Removed duplicate `applyTheme()` call** from the main.js IIFE — it now only syncs the theme-toggle icon.

**Why:** Without step 1, there is always a flash window between HTML parse and JS execution. Without step 2, Bootstrap components (modals, dropdowns, cards) briefly render in Bootstrap's default white.

**How to apply:** If adding a new theme variant, update BOTH the inline script fallback AND the Bootstrap overrides block in CSS.
