# Expansions Static Site Generator — Plan

## Goal

Build a new `expansions/` sub-project under `TI` that generates beautiful,
self-contained static HTML sites for individual Twilight Imperium expansions.

Each expansion site shares the dark, card-first visual style of the existing
`card_diff` report but is richer and more featureful:

- No comparison view — it presents one expansion's full content.
- Static JS search, filtering, and sorting.
- Rich sections: overview, rules, FAQs, components, factions, technologies, units, etc.
- Generated from structured data so the site is reproducible and versionable.

## Workflow

1. **Collect** — A local web editor (form-based) gathers all expansion data,
   source folders, rules, FAQs, and metadata.
2. **Structure** — The editor writes `config.json` and `expansion-overview.md`.
3. **Generate** — A Python generator reads `config.json` and the templates and
   emits a standalone static site.
4. **Prompt** — `expansion-overview.md` is designed to be pasted into an agent
   prompt to build custom pages or new features from the templates.

## Directory Structure

```
TI/expansions/
├── PLAN.md                 # This document
├── README.md               # User-facing setup & usage guide
├── generator/              # Python generator scripts
│   ├── __init__.py
│   ├── site.py             # Main entry point: build_site(config_path)
│   ├── config.py           # Load and validate config.json
│   ├── templates.py        # Jinja2 template loader
│   ├── assets.py           # Copy images, css, js into output
│   └── md_prompt.py        # Build agent prompt from expansion-overview.md
├── editor/                 # Local web editor (forms)
│   ├── app.py              # Flask or FastAPI app
│   ├── static/
│   │   ├── css/
│   │   └── js/
│   ├── templates/
│   └── data/               # Saved editor sessions
├── templates/              # Shared site templates
│   ├── base.html
│   ├── index.html
│   ├── components/
│   │   ├── nav.html
│   │   ├── card.html
│   │   ├── search.html
│   │   └── filter-bar.html
│   ├── css/
│   │   └── styles.css      # Shared dark theme (borrowed from card_diff)
│   └── js/
│       ├── search.js       # Static JS search index
│       ├── filters.js      # Filter / sort UI
│       └── ui.js           # Common interactions
├── schema/
│   └── expansion.json      # JSON schema for config.json
├── source/                 # Source assets for expansions
│   ├── monuments/
│   └── keleres+/
│       └── src/            # Source images / assets
└── sites/                  # Generated static sites
    └── example_monuments/
        ├── index.html
        ├── assets/
        │   ├── css/
        │   ├── js/
        │   └── images/
        └── data/           # Optional JSON data files for JS search
```

## Key Features

### Visual Style

- Reuse the dark theme from `card_diff` (`#0f1117` background, `#1a1d27` cards,
  `#2d3148` borders, system font stack).
- Card components with rounded corners, hover states, and icon pills.
- Responsive layout.

### Static JS Search

- Build a search index JSON at generation time (e.g., lunr.js compatible or a
  simple custom inverted index).
- Client-side search across card names, abilities, rules, FAQs, etc.

### Filtering & Sorting

- Filter by category (faction, technology, unit, component, etc.), icon,
  ability, cost, etc.
- Sort by name, cost, complexity, etc.

### Local Editor

- Web forms for each expansion section.
- Drag-and-drop or directory picker for source image folders.
- Live preview of the generated site.
- Export button writes `config.json` + `expansion-overview.md`.

### Agent Prompt

- `expansion-overview.md` is a human-readable summary.
- `md_prompt.py` can combine it with template snippets into a prompt for an agent
  to generate custom pages or new features.

## Phases

### Phase 1 — Foundation

- Create directory structure.
- Add JSON schema for `config.json`.
- Port shared CSS/JS from `card_diff`.
- Create `base.html` and `index.html` templates.
- Implement `generator/site.py` to build a basic static site from a sample config.

### Phase 2 — Editor

- Build local editor app with forms.
- Generate `config.json` and `expansion-overview.md`.
- Add live preview.

### Phase 3 — Rich Content

- Add components for factions, tech, units, action cards, promissories, etc.
- Add static search index.
- Add filtering and sorting.

### Phase 4 — Polish & Examples

- Create example expansion config.
- Add tests for config validation.
- Document end-to-end workflow.

## Configuration Schema (config.json)

```json
{
  "id": "monuments",
  "name": "Monuments",
  "version": "3.1",
  "description": "Monuments expansion overview",
  "release_date": "2026-06-01",
  "source": {
    "images": "source/monuments/Monuments",
    "icons": "source/monuments/icons"
  },
  "sections": [
    {
      "id": "overview",
      "title": "Overview",
      "type": "markdown",
      "content": "overview.md"
    },
    {
      "id": "factions",
      "title": "Factions",
      "type": "cards",
      "items": [
        {
          "id": "argent",
          "name": "Argent Flight",
          "image": "factions/argent.jpg",
          "summary": "...",
          "tags": ["flight", "trade"]
        }
      ]
    }
  ]
}
```

## Git Plan

1. Commit the current `TI` project as the initial base.
2. Push to `https://github.com/Cacotopos/TI.git` (new repository).
3. Create branch `feature/expansions`.
4. Implement Phase 1 and open a PR when ready.

## Open Questions

- Should the editor use Flask or FastAPI?
- Should we use Jinja2 for templating, or plain string templates?
- Should the search index be lunr.js compatible or custom?
