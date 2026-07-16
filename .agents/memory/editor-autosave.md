---
name: Editor Autosave Race Fix
description: loadChapter is async; chapter ID is captured before switching to prevent dirty-state clobber.
---

## Problem
`loadChapter()` called `saveCurrentChapter(true)` (fire-and-forget, no await), then immediately changed `currentChapterId`. When the save resolved, it used the NEW `currentChapterId` to update the sidebar and reset `isDirty` — clearing dirty state for the chapter the user just switched to.

## Fix
- `loadChapter` is now `async`.
- Before switching, captures `savingId = currentChapterId` and sets `isDirty = false` to prevent re-entry.
- Awaits `saveCurrentChapter(true, savingId)` with the explicit old chapter ID.
- `saveCurrentChapter` accepts an optional `chapterId` param; only resets `isDirty` if `targetId === currentChapterId`.

**Why:** Race-free saves must use immutable IDs captured at call-time, not globals that change during async execution.
