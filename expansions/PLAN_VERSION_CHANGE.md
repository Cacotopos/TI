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

1. **Two source inputs** — local folder paths, each with a free-text
   **label** describing the source (e.g. `Monuments v3.0`,
   `Monuments v3.1`). Google Drive folders are out of scope — files are
   synced/downloaded to local paths first (locally-synced Drive folders
   under `~/Library/CloudStorage/` already work as plain paths).
   Reuse the existing folder-picker button.
2. **Compare** — loads image files in both folders and does a file-level
   diff (MD5 of file bytes):
   - **Changes detected** — files that differ, files only in one side
     (new / removed), and ambiguous files that couldn't be confidently
     paired.
   - **Unchanged** — identical files (listed by file name).
3. **Changed files are clickable** — same interaction pattern as the Images
   tab: clicking a changed file opens a modal showing the two diffed images
   side by side.
4. **Modal annotation fields**:
   - Free-text input — the author manually describes the differences.
   - **Change type** dropdown (severity):
     `new / removed / minor / moderate / major / replacement`.
   - **Aspects checklist**: `title`, `art`, `layout`, `flavor`, `ability`,
     `placement` — which facets of the file changed.
   - **"Unchanged" checkbox** — marks a false positive and moves it back to
     the unchanged list.
5. **Persistence** — changelog data is saved in a **separate `changes.json`**
   alongside `config.json` in `editor/data/<expansion>/`, so the main config
   stays lean. Save/Load reads and writes both files together.

## File Matching Algorithm

- **Only image files** are compared — same extension set as the image
  scanner (`jpg/jpeg/png/webp/gif/bmp`). PDFs, txt, zips are ignored.
- **Match primarily by filename.** When a filename exists exactly once in
  each folder, the files pair up.
- **Filename collisions** (same name in multiple subfolders) are resolved
  using the relative folder path — pair the entries whose relative
  directories match.
- **Err on the side of "change"**: anything that can't be paired
  confidently is listed under Changes Detected rather than silently dropped.
  Human review marks false positives via the modal's Unchanged checkbox.
- Left-only files → `removed`; right-only files → `added`; paired files
  with different MD5s → `changed`.

### Follow-up (deferred): ambiguous-pair reconciliation

Files that can't be auto-paired (e.g. same filename in several folders on
one side, or a file moved to a new folder) are surfaced under Changes
Detected with an "unpaired" flag. A later iteration can add a manual "pair
with…" picker in the modal so the author can join a specific left file to a
specific right file; until then they can be annotated as `removed`/`added`
or marked unchanged as appropriate.

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

- `status`: `added | removed | changed | unchanged` (set by the diff; the
  Unchanged checkbox stores `false_positive: true` on a `changed` entry).
- `files` keyed by path relative to the source root.
- `changes.json` is loaded/saved with the expansion and read by the
  generator at build time.

## Backend Work (`app.py`)

- `GET /api/changes/<expansion_id>` — return `changes.json` (empty object if
  absent).
- `POST /api/changes/<expansion_id>` — persist `changes.json`.
- `POST /api/changelog/compare` — body: `{left: {label, path}, right:
  {label, path}}`. Scans both folders for image files, hashes each file
  (MD5), applies the matching algorithm above, and returns `{added, removed,
  changed, ambiguous, unchanged}` keyed by relative path (with both-side
  dimensions for thumbnails).
- Image preview route for changelog sources — e.g.
  `/api/changelog/image/<side>/<path>` serving from the configured left/right
  folders, reusing the existing EXIF-stripping preview logic so modal images
  match generated output.

## Editor UI (`editor.html`)

- New `.tab` + `tab-select` option "Changelog Page" after *Change History*.
- Tab content:
  - Two source rows: label input + folder path input + Pick folder button.
  - Compare button; result lists "Changes detected" and "Unchanged".
  - Changed-file grid styled like the Images tab (thumbnail, filename,
    change-type badge, unpaired flag where applicable).
  - Diff modal: side-by-side old/new images, change-type select, aspects
    checklist, notes field, "Unchanged" checkbox.
- `save()` also POSTs `changes.json`; `tryLoadConfig` / `resetForm` load and
  reset both documents.

## Generated Site (`site.py` + templates)

- `build_site` reads `changes.json` next to the config (accept an optional
  `--changes` path override).
- **Changelog images are copied into the site** — the old-version images
  are not part of normal site assets, so both sides of each published change
  are copied under `assets/changelog/` (e.g. `assets/changelog/old/...`,
  `assets/changelog/new/...`) so they content-hash, deploy, and serve
  normally.
- New `expansions/templates/changelog.html` extending `base.html`:
  - Heading from the two labels.
  - **Filter toolbar** (same pattern as the search page / Images tab):
    - Text search over filename and notes.
    - Severity filter — one toggle per `change_type`
      (new/removed/minor/moderate/major/replacement).
    - Aspect filter — one toggle per aspect
      (title/art/layout/flavor/ability); an entry matches if it has *any*
      selected aspect.
    - A visible count of matched entries.
  - A compact list of entries grouped by `change_type` severity order
    (new → major → moderate → minor → replacement → removed), each showing
    filename, severity badge, changed-aspect badges, and author notes.
  - **Click-to-compare**: clicking an entry opens a modal with the old and
    new images side by side — same interaction pattern as the card modal.
  - False-positive / unchanged entries are excluded from the page.
  - Filtering is client-side: entries render with `data-*` attributes
    (`data-change-type`, `data-aspects`, filename, notes) and a small
    `changelog.js` (or an extension of `filters.js`) toggles visibility —
    no server round-trips, consistent with `search.js`/`filters.js`.
- `base.html` nav: append a "Changelog" link labelled
  `Changelog {label1} → {label2}` at the far right, in both desktop nav and
  the mobile `<select>`, only when a changelog exists.
- Include the published changelog entries in `data.json` for external
  consumers.

## Work Items

1. `changes.json` load/save endpoints (`app.py`).
2. `POST /api/changelog/compare` — image scan, MD5 diff, filename-primary /
   folder-path-disambiguated matching.
3. Changelog-source image-serving route for editor modal previews.
4. Editor tab + compare UI + clickable results grid + annotation modal.
5. Wire `changes.json` into `save()` / `tryLoadConfig` / `resetForm`.
6. Copy paired changelog images into `assets/changelog/` during generation.
7. `changelog.html` template (click-to-compare modal + severity/aspect/text
   filters) + `site.py` integration + nav link in `base.html` + `data.json`
   export.
8. README section documenting the tab and file format.
9. *(Follow-up)* Manual pair picker for ambiguous/unpaired files.

## Deferred

- Real Google Drive integration (shareable links/folder IDs) — the author
  downloads/syncs folders locally instead.
- Perceptual image diffing — v1 compares raw bytes (MD5); re-encoded but
  visually identical files show as changed and are cleared with the
  Unchanged checkbox.
- Multiple version pairs — v1 stores a single `v3.0 → v3.1` pair.

## Outstanding tasks (unrelated findings)

- **`data.json` image paths don't resolve.** `_build_export` emits clean
  `front`/`back` paths (`assets/images/Foo.jpg`), but filename hashing
  renames the deployed files (`Foo.v2-<hash>.jpg`), so every image
  reference in the public `data.json` 404s. To be usable as a game-engine
  export it should either emit resolved hashed URLs or ship a stable
  un-hashed image path. Text fields (`overview`/`description`/`faq`) are
  also rendered HTML — raw markdown would be more useful for ingestion.
