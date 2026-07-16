---
name: Save Blank-Overwrite Guard
description: The chapter save route rejects blank content when the chapter already has words, preventing accidental clearing.
---

## Rule
`POST /project/<id>/editor/chapter/<id>/save` returns HTTP 400 if:
- `content` key is missing entirely from the request body, OR
- `content.strip() == ''` AND the chapter's existing `word_count > 0`

Empty content is only accepted for chapters that are already empty (word_count == 0).

**Why:** Autosave fires on a 3-second debounce. A JS bug or network hiccup delivering an empty payload would silently wipe a chapter. The guard is server-side so no client-side workaround can bypass it.
