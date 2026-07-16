---
name: Generation Button Wiring
description: btnStart has NO inline onclick — single click path via JS listener that routes start vs resume.
---

## Rule
`templates/generation.html` — `#btnStart` has no `onclick` attribute. All click logic lives in `static/js/generation.js` DOMContentLoaded listener:
```js
startBtn.addEventListener('click', function() {
  const status = this.dataset.status || window.PROJECT_STATUS_CURRENT || 'draft';
  if (status === 'paused') resumeGeneration();
  else startGeneration();
});
```

**Why:** Having both an inline `onclick="startGeneration()"` AND a JS addEventListener caused double-firing: normal starts sent two API requests, and paused-resume sent a start + a resume simultaneously, causing race conditions.

**How to apply:** Never add `onclick` attributes to #btnStart, #btnPause, or #btnStop — those are all wired in generation.js. Pause and stop still use onclick in the template because they don't have conditional routing logic.
