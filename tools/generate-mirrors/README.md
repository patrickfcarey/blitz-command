# generate-mirrors

One-shot generator that creates left-handed mirrors of every right-handed offensive formation in `data/formations/`.

## When to run

- After adding a new right-handed formation that needs a left-handed counterpart
- When you want to regenerate mirrors after updating the originals

The script does not overwrite existing mirror files — it warns and skips. To regenerate a specific mirror, delete it first.

## What it does

For each formation file `<stem>.yaml` (excluding symmetric formations like `full-house` and existing `-left` mirrors):

- Flips x coordinates of all non-OL players (OL labels stay symmetric)
- Flips `strength_side` (right ↔ left; `balanced` stays balanced)
- Updates the `name` field (`Right` → `Left`, else appends ` Left`)
- Appends a breadcrumb to `source_notes` recording the mirror operation
- Writes to `<stem>-left.yaml` (or `<stem>` with `right`→`left` for files like `shotgun-trips-right` → `shotgun-trips-left`)

## Run

```
python3.11 tools/generate-mirrors/generate.py
```

(Uses pyyaml — install via `tools/coordinate-translator/requirements.txt` or any other repo venv.)

## Caveats

- The original `notes` field may describe the right-handed look in narrative form. The mirror keeps that narrative as-is; the new `source_notes` breadcrumb tells the reader "coords are flipped — narrative may not be."
- Output uses default `yaml.safe_dump` formatting, which differs from the inline-mapping style used in hand-written formation files. Functionally equivalent, just visually different.
