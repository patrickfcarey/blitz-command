# Formation Legality Rules

Rules that every offensive (and defensive) formation in `data/formations/` must obey to be a legal football formation. These apply at every level — high school, college, NFL — with only minor variations noted inline.

The schema (`schemas/formation.schema.json`) enforces structural correctness (11 players, required fields). The rules in this document are the *football* correctness checks the schema can't enforce alone — a play designer or generator MUST follow them when laying players out.

---

## Offensive formation rules

### Rule 1 — Exactly 7 players on the line of scrimmage

Of the 11 offensive players, **exactly 7 must be on the line of scrimmage** (LOS) at the snap.

In our data, that's `players[*].on_line == true` count == 7. The remaining 4 (the "backfield") have `on_line: false`.

The "line of scrimmage" in our universal coordinate system is `y = 0`. A player is *on* the line when their head/torso breaks the line of the ball — in practice, set `y` close to 0 (we use exactly `0.0`) and `on_line: true`.

A player off the line must be at least 1 yard back (`y ≤ -1.0`). The rule is more lenient than 1 yard in practice (anything that doesn't visually break the line counts), but 1 yard keeps coordinates clean and avoids ambiguity.

### Rule 2 — The two end-of-line players must be eligible receivers

This is the rule a lot of generated formations get wrong. **The leftmost and rightmost players on the line of scrimmage must be eligible receivers** (TE or WR), not interior offensive linemen.

Why: only eligible receivers can catch a forward pass. Putting an interior OL at the end of the line would mean that "end" isn't catchable, which the rule disallows. It also prevents "tackle-eligible" disguises without reporting.

In our data: among players with `on_line: true`, find the one with the smallest `x` and the one with the largest `x`. Both `position` values must be `WR` or `TE`. The 5 OL positions (`LT`, `LG`, `C`, `RG`, `RT`) cannot be the leftmost or rightmost on-line player.

**Practical examples:**

| Formation | Leftmost on-line | Rightmost on-line | Legal? |
|-----------|------------------|-------------------|--------|
| I-Form (TE right) | X (WR, x=-15) | TE (TE, x=3.5) | ✓ |
| Trips Right (TE left) | TE (TE, x=-3.5) | WR1 (WR, x=15) | ✓ |
| Big I (2 TE) | TE-L (TE, x=-3.5) | TE-R (TE, x=3.5) | ✓ |
| Empty 5-wide | X (WR) | Z (WR) | ✓ |
| Full House (2 TE, no WR) | TE-L (TE, x=-3.5) | TE-R (TE, x=3.5) | ✓ |
| **All 5 OL + 2 TE on inside, WRs off** | **LT (OL)** | **RT (OL)** | **✗ ILLEGAL** |

If you want a formation with 7 OL-style blockers on the line (e.g. tackle-over), you must either (a) report a tackle as eligible to the official, or (b) use a TE wider than the original tackle so the *TE* is the line end — which is what jumbo / unbalanced lines do.

### Rule 3 — At most 5 eligible receivers numbered as such

At any time, **at most 5 offensive players can wear eligible jersey numbers** (NCAA: 1–49 and 80–99; NFL similar with reporting allowances). Eligibles are:

- The two end-of-line players (Rule 2)
- All four players in the backfield (`on_line: false`), one of whom is the QB

That's potentially 6 positions but only 5 can be "live" eligibles at once. In practice, the QB is one of the 4 backs, leaving 5 distinct eligible *receivers*: 2 line-ends + 3 non-QB backs.

For our 11-personnel and 21-personnel formations this works out automatically. For unusual formations (e.g. 5 WR Empty), the count must still be 5 eligibles plus the QB.

### Rule 4 — Five interior offensive linemen

The **5 interior linemen** (`LT`, `LG`, `C`, `RG`, `RT`) are always on the line, always ineligible by number (50–79 in NFL/NCAA), and form the interior of the line. They cannot be the end-of-line players (see Rule 2).

In our data: every formation has exactly one `C`, one `LG`, one `RG`, one `LT`, one `RT`, all with `on_line: true`.

### Rule 5 — Setting before snap

A player who shifts or motions must be set (motionless) for **1 second before the snap** (NFL) or **be one of one motioning player going parallel/backward** (NCAA). This rule shapes pre-snap motion design but doesn't affect the static formation file. It belongs in the play schema (`motions` field) when that's built.

---

## Practical pre-flight checklist for any new formation

Before saving a new file in `data/formations/`, confirm:

- [ ] Exactly 11 players in `players[]`
- [ ] Exactly 7 players have `on_line: true`
- [ ] Exactly one of each interior OL position: `LT`, `LG`, `C`, `RG`, `RT`
- [ ] All 5 interior OL have `on_line: true`
- [ ] The leftmost on-line player (smallest `x` with `on_line: true`) is a TE or WR
- [ ] The rightmost on-line player (largest `x` with `on_line: true`) is a TE or WR
- [ ] Off-line players have `y ≤ -1.0` (at least 1 yard back)
- [ ] Personnel string matches actual counts (e.g. "21" = 2 RB + 1 TE + 2 WR)

A `validate-formation-rules` tool that automates this checklist is on the roadmap (it's strictly more than `formation.schema.json` can verify — JSON Schema can't express "leftmost on-line player must have position in {TE, WR}").

---

## Defensive formation rules

Defensive formations are far less constrained:

- 11 players (always)
- No on-line / off-line restrictions (defense can line up anywhere on their side of the LOS)
- The defensive line cannot encroach across the neutral zone before the snap
- Numbering is unrestricted for receiving purposes (defense doesn't catch forward passes from the offense)

Defensive formation files use the same schema but `side: defense`. Personnel uses front-LB shorthand (`4-3`, `3-4`, `nickel`, `dime`).

---

## Game-engine considerations

Some game editors enforce subsets of these rules automatically (won't let you save an illegal formation), and some don't:

- **Modern editors (Madden / NCAA mid-2000s+)**: typically block illegal saves
- **Older editors (PS1-era)**: may allow illegal alignments that the engine then handles oddly

When in doubt, treat the rules above as the authoritative truth and let the per-game `editor-grid.yaml` document the editor's actual enforcement.

---

## References

- NFL Rulebook, Rule 7 (Snap), Rule 5 (Position of Players at Snap)
- NCAA Football Rules, Rule 7-1
- Standard offensive football coaching texts (Bill Walsh, Tom Osborne, Homer Smith)
