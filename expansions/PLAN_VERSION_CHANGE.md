# Plan — Changelog Page (branch: `version-change`)

## Goal

Add a new **"Changelog Page"** tab in the editor (next to *Change History*)
that diffs two versions of an expansion's source folder, lets the author
annotate each changed file, and renders a public **Changelog** page on the
generated site:

```
Changelog {source-1 label} → {source-2 label}
```

e.g. `Changelog Monuments v3.0 → Monuments v3.1`, placed at the far right of
the site nav (desktop menu and mobile dropdown).

## Editor Flow (Changelog Page tab)

1. **Two source inputs** — each takes a local folder path or a Google Drive
   folder, plus a free-text **label** describing the source
   (e.g. `Monuments v3.0`, `Monuments v3.1`).
2. **Compare** — loads the files in both folders and does a file/image diff,
   matching files by name:
   - **Changes detected** — files that differ, plus files only in one side
     (new / removed).
   - **Unchanged** — identical files (listed by file name).
3. **Changed files are clickable** — same interaction pattern as the Images
   tab: clicking a changed file opens a modal showing the two diffed images
   side by side.
4. **Modal annotation fields**:
   - Free-text input — the author manually describes the differences.
   - **Change type** dropdown (severity):
     `new / removed / minor / moderate / major / replacement`.
   - **Aspects checklist**: `title`, `art`, `layout`, `flavor`, `ability` —
     which facets of the file changed.
   - **"Unchanged" checkbox** — marks a false positive and moves it back to
     the unchanged list.
5. **Persistence** — changelog data is saved in a **separate `changes.json`**
   alongside `config.json` in `editor/data/<expansion>/`, so the main config
   stays lean. Save/Load reads and writes both files together.

## Data Model — `editor/data/<expansion>/changes.json`

```json
{
  "sources": [
    { "label": "Monuments v3.0", "path": "/abs/path/to/v3.0" },
    { "label": "Monuments v3.1", "path": "/abs/path/to/v3.1" }
  ],
  "files": {
    "Monuments/BR/Atokera.jpg": {
      "status": "changed",
      "change_type": "moderate",
      "aspects": ["art", "ability"],
      "notes": "New art; ability text reworded.",
      "false_positive": false
    },
    "Tokens/Creuss Back.png": {
      "status": "removed",
      "change_type": "removed",
      "aspects": [],
      "notes": "",
      "false_positive": false
    }
  }
}
```

- `status`: `changed | added | removed | unchanged`.
- `files` keyed by path relative to the source root.
- `changes.json` is only reloaded/saved with the expansion — it is also read
  by the generator at build time.

## Backend Work (`app.py`)

- `GET /api/changes/<expansion_id>` — return `changes.json` (empty object if
  absent).
- `POST /api/changes/<expansion_id>` — persist `changes.json`.
- `POST /api/changelog/compare` — body: `{expansion_id, left: {label, path},
  right: {label, path}}`. Scans both folders, hashes each file (MD5), and
  returns `{added, removed, changed, unchanged}` lists keyed by relative
  path.
- Image preview for arbitrary changelog folders — extend `/api/image` or add
  `/api/changelog/image/<side>/<path>` that serves from the configured
  changelog source folders (reusing the existing EXIF-stripping preview
  logic), so modal images match generated output.

## Editor UI (`editor.html`)

- New `.tab` + `tab-select` option "Changelog Page" after *Change History*.
- Tab content:
  - Two source rows (label + folder path + optional Drive link, with the
    existing folder-picker button).
  - Compare button; result lists "Changes detected" and "Unchanged".
  - Changed-file grid styled like the Images tab (thumbnail, filename,
    change-type badge).
  - Diff modal: side-by-side old/new images, change-type select, aspects
    checklist, notes field, "Unchanged" checkbox.
- `save()` also POSTs `changes.json`; `tryLoadConfig` / `resetForm` load and
  reset both documents.

## Generated Site (`site.py` + templates)

- `build_site` reads `changes.json` next to the config (accept
  `--changes path` override).
- New `expansions/templates/changelog.html` extending `base.html`:
  - Title/heading from the two labels.
  - Sections grouped by `change_type` severity order
    (new → major → moderate → minor → replacement → removed).
  - Each entry: filename, old vs new images side by side, severity badge,
    changed-aspect badges, author notes.
  - False-positive / unchanged entries are excluded from the page.
- `base.html` nav: append "Changelog {label1} → {label2}" link at the far
  right (after Search/Ko-fi position per existing layout), in both desktop
  nav and the mobile `<select>`, only when a changelog exists.
- Include `changelog` data in `data.json` export for external consumers.

## Work Items

1. `changes.json` schema + load/save endpoints (`app.py`).
2. `POST /api/changelog/compare` folder-diff endpoint (MD5 by relative path).
3. Changelog-source image-serving route for modal previews.
4. Editor tab + compare UI + clickable results grid + annotation modal.
5. Wire `changes.json` into `save()`/`tryLoadConfig`/`resetForm`.
6. `changelog.html` template + `site.py` integration + nav link in
   `base.html` + `data.json` export.
7. README section documenting the tab and file format.

## Open Questions

1. **Google Drive folders** — does "g-drive folder" mean a locally-synced
   Drive path (works today as a local path under `~/Library/CloudStorage/`),
   or a shareable Drive link/ID? Real Drive links need the Drive API +
   auth and are deferred unless required.
2. **File matching** — match by relative path (recommended) or bare
   filename? Relative path keeps folder structure; filename-only matching
   would falsely pair files moved between folders.
3. **Diff method** — v1 compares raw bytes (MD5). Re-encoded but visually
   identical files show as changed; the "Unchanged" checkbox is the escape
   hatch. Perceptual image diffing is deferred.
4. **Renamed files** — a renamed file appears as removed + added. The
   `replacement` change type can be used to describe this manually.
5. **Multiple version pairs** — v1 stores a single source pair
   (`v3.0 → v3.1`). Chaining several pairs is deferred.
