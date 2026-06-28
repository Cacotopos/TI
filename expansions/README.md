# TI Expansions Static Site Generator

Generates rich, self-contained static HTML sites for individual Twilight
Imperium expansions.

## Quick Start

```bash
cd /Users/kangarootime/Source/RiderProjects/TI/expansions

# Run the local editor to collect expansion data
python3 editor/app.py

# Then open http://localhost:3030

# Generate the static site
python3 generator/site.py examples/example_monuments/config.json --output sites/example_monuments

# Open the site
open sites/example_monuments/index.html
```

## Overview

This sub-project is separate from `card_diff` but shares its visual language.
Instead of comparing two versions, an expansion site presents one expansion's
full content with search, filtering, and rich sections.

The workflow is:

1. **Editor** (`editor/`) — Web forms collect expansion data and produce
   `config.json` + `expansion-overview.md`.
2. **Generator** (`generator/`) — Reads the config and templates and emits a
   standalone static site.
3. **Site** (`sites/`) — A self-contained HTML/CSS/JS site ready for S3 or any
   static host.

See `PLAN.md` for the full design.
