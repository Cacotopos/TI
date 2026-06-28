# TI Expansions Static Site Generator

Generates rich, self-contained static HTML sites for individual Twilight
Imperium expansions.

## Quick Start

```bash
cd /Users/kangarootime/Source/RiderProjects/TI/expansions

# Run the local editor
python3 editor/app.py

# Open the editor
open http://localhost:3030

# Generate a static site from a saved config
python3 -m expansions.generator.site editor/data/monuments/config.json --output sites/monuments

# Open the generated site
open sites/monuments/index.html
```

## Overview

This sub-project is separate from `card_diff` but shares its dark, card-first
visual style. Instead of comparing two versions, an expansion site presents one
expansion's full content with search, sections, and rich card details.

## Workflow

1. **Source assets** — Place expansion images under `source/<expansion>/`.
2. **Editor** — Open `http://localhost:3030`, choose an existing expansion or
   type a new ID, fill in metadata, and inspect the source folder to build the
   asset map.
3. **Configure assets** — For each detected image, set title, section, group,
   description, FAQ, back image, hidden flag, and whether it is a card.
4. **Sections** — Add or edit sections. Inspecting a folder auto-suggests
   sections from top-level subfolders.
5. **Save** — Writes `editor/data/<expansion>/config.json`.
6. **Generate** — Produces a standalone static site under `sites/<expansion>/`.
7. **Deploy** — Uploads the generated site to the configured S3 bucket.

## Asset Model

The editor stores every detected image as an entry in `config.json`:

```json
{
  "assets": {
    "Monuments/BR/Atokera.jpg": {
      "id": "Atokera",
      "path": "Monuments/BR/Atokera.jpg",
      "folder": "Monuments/BR",
      "configured": false,
      "hidden": false,
      "isCard": true,
      "type": "other component",
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

- `configured` — Set to true once you have reviewed the asset.
- `hidden` — Excluded from the generated site.
- `type` — One of: public objective, secret objective, promissory note, agent, commander, hero, alliance, action card, scenario, other component, agenda, relic, planet, tile, token, relic fragment, legendary ability, planet ability, station, rulebook.
- `faction` — Optional faction name. The dropdown is populated from distinct faction values across the expansion, but you can type any value.
- `section` — Which generated page the card appears on.
- `group` — Used to render cards in named groups on the page.
- `back` — Path to the back image for two-sided cards.

## Banner Image

You can optionally set a wide banner image for the expansion. The editor lists
source images that are at least 1552px wide (central column of 1152px plus
200px on each side). The generator skips banners that are too narrow. The
banner is displayed full-width at the top of every page, centered and
repeating horizontally.

## Directory Structure

```
expansions/
├── editor/                 # Local web editor
│   ├── app.py              # Flask app
│   ├── data/               # Saved configs
│   │   ├── monuments/
│   │   └── keleres+/
│   └── templates/
│       └── editor.html     # Editor UI
├── generator/              # Static site generator
│   ├── __init__.py
│   └── site.py             # build_site(config_path, output_dir)
├── templates/              # Shared Jinja2 templates and assets
│   ├── base.html
│   ├── index.html
│   ├── section.html
│   ├── section_cards.html
│   ├── search.html
│   ├── css/styles.css
│   └── js/
│       ├── search.js
│       ├── ui.js
│       └── cards.js
├── source/                 # Source images per expansion
│   ├── monuments/
│   └── keleres+/
├── sites/                  # Generated static sites
│   ├── monuments/
│   └── keleres+/
├── schema/                 # JSON schema for config.json
├── README.md               # This file
└── PLAN.md                 # Design and implementation notes
```

## Image Cropping

Card images are cropped using the same mask as the `card_diff` project
(`Icons/Card Mask.png`). The generator copies source images to the output site
and applies the mask bounding box so cards render cleanly.

## Search

The generated site includes a static JS search page that indexes section
titles, expansion overview, and asset names, descriptions, and FAQ content.
