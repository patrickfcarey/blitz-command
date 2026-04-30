# generate-mirror-plays

One-shot generator that creates left-handed mirrors of every right-handed play.

Mirrors:
- Path waypoints (negated on x)
- Motion end positions (negated on x)
- Formation reference (points to the mirror formation)
- play_id and name (`Right` → `Left`, else appends)
- Adds a breadcrumb to source_notes

Does NOT touch routes — they're already mirror-aware via the drawing tool's receiver-side detection.

## Run

```
python3.11 tools/generate-mirror-plays/generate.py
```

Skips any mirror that already exists. To regenerate, delete the target file first.

## Requirements

The mirror formation file must exist. The companion tool `tools/generate-mirrors/` handles that for formations.
