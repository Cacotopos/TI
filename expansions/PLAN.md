# Expansions Static Site Generator — Plan

## Goal

The `expansions/` sub-project generates beautiful, self-contained static HTML
sites for individual Twilight Imperium expansions.

Each site shares the dark, card-first visual style of the existing `card_diff`
report but presents one expansion's full content:

- Sections and navigation.
- Static JS search across metadata, sections, and card details.
- Grouped card galleries with click-to-expand detail panels.
- FAQ and back-image support for individual cards.
- Reproducible, versionable generation from `config.json`.

## Workflow

1. **Source assets** — Place expansion images under `source/<expansion>/`.
2. **Editor** — Start the local web editor, choose an existing expansion or create
   a new ID, and fill in metadata.
3. **Inspect** — Click **Inspect Folder** to scan the source folder and create an
   `assets` map for every detected image.
4. **Configure** — For each asset, set title, section, group, description, FAQ,
   back image, whether it is a card, and whether it is hidden.
5. **Save** — Writes `editor/data/<expansion>/config.json`.
6. **Generate** — Produces a standalone static site under `sites/<expansion>/`.
7. **Deploy** — Uploads the generated site to S3 from the editor.

## Directory Structure

```
TI/expansions/
├── PLAN.md                 # This document
├── README.md               # User-facing setup & usage guide
├── generator/              # Python static site generator
│   ├── __init__.py
│   └── site.py             # build_site(config_path, output_dir)
├── editor/                 # Local web editor
│   ├── app.py              # Flask app
│   ├── templates/
│   │   └── editor.html     # Single-page editor UI
│   └── data/               # Saved expansion configs
│       ├── monuments/
│       └── keleres+/
├── templates/              # Shared Jinja2 templates and assets
│   ├── base.html
│   ├── index.html
│   ├── section.html
│   ├── section_cards.html
│   ├── search.html
│   ├── css/styles.css
│   └── js/
│       ├── search.js       # Static JS search index
│       ├── ui.js           # Search UI wiring
│       └── cards.js        # Card detail modal
├── schema/
│   └── expansion.json      # JSON schema for config.json
├── source/                 # Source images per expansion
│   ├── monuments/
│   └── keleres+/
└── sites/                  # Generated static sites
    ├── monuments/
    └── keleres+/
```

## Implemented Features

### Editor

- Single-page editor with expansion selector.
- Dropdown prepopulated from `source/` and `editor/data/` subfolders.
- New expansion IDs typed manually.
- Expansion metadata form (name, version, description, overview, source folder,
  S3 path).
- Section editor with add/remove and id/title/type fields.
- Asset inspection with auto-suggested sections from top-level folders.
- Asset list with "not configured" and "hidden" filters and a search box.
- Per-asset modal with image preview, filename, title, section, group, type,
  faction, description, FAQ, back image, physical `component`, `hidden`, and `configured`
  flags.
- Optional banner image picker with minimum width validation.

### Generator

- Jinja2 templating.
- Copies CSS, JS, and images into the output site.
- Crops card images per physical component using `Icons/Card Mask.png` (US Mini)
  and component-specific masks for Tarot and Poker.
- Generates `index.html`, one page per section, and a `search.html` page.
- Writes `data.json` for client-side search.
- Groups cards by their `group` field on section pages.
- Respects `section` and `hidden` flags.

### Generated Site

- Shared dark theme with Tailwind CDN.
- Sticky navigation bar with section links and search.
- Card grids grouped by folder or custom group.
- Click-to-expand card detail modal with description, FAQ, and back image.
- Static search page with inverted index and tokenized scoring.
- Optional full-width banner image at the top of every page, centered and
  tiled horizontally.

## Configuration Schema (config.json)

```json
{
  "id": "monuments",
  "name": "Monuments",
  "version": "3.1",
  "description": "A structures expansion for Twilight Imperium 4th edition...",
  "overview": "An introduction page and overview...",
  "source": {
    "images": "expansions/source/monuments"
  },
  "s3_path": "monuments",
  "banner": {
    "path": "expansions/source/monuments/banner.jpg"
  },
  "sections": [
    { "id": "overview", "title": "Overview", "type": "markdown" },
    { "id": "cards", "title": "Cards", "type": "cards" }
  ],
  "assets": {
    "Monuments/BR/Atokera.jpg": {
      "id": "Atokera",
      "path": "Monuments/BR/Atokera.jpg",
      "folder": "Monuments/BR",
      "configured": false,
      "hidden": false,
      "isCard": true,
      "type": "Other Component",
      "faction": "",
      "title": "Atokera",
      "description": "",
      "faq": [],
      "section": "cards",
      "group": "Monuments/BR",
      "back": ""
    }
  }
}
```

## Future Improvements

- Markdown content sections with editable body text.
- Rich non-card components (factions, technologies, units, action cards).
- Advanced filtering and sorting UI.
- Validation against `schema/expansion.json`.
- Live preview in the editor.
- Batch editing of assets (multi-select for section/group assignment).
- Drag-and-drop or directory picker for source image folders.
- `expansion-overview.md` prompt export for agent-driven custom pages.
