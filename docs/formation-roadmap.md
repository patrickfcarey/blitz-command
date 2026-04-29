# Formation & Play Coverage Roadmap

Comprehensive list of formations and play families across HS / college / pro football, with status:

- **(have)** — file exists in `data/formations/` or `data/plays/`
- **(this batch)** — being added in the current build pass
- **(next)** — planned for the immediate next pass
- **(future)** — known but lower priority

When this list grows out of date, update it. Cross-reference for "what's missing."

---

## Offensive formations

### I-Formation family (under-center, 2 RB stacked)

- I-Formation **(have)** — base 21 personnel, TE-strong
- Strong I **(have)** — FB offset strong
- Weak I **(have)** — FB offset weak
- Big I **(have)** — 22 personnel, 2 TE
- I-Form Twins Weak **(have)** — both WRs opposite TE
- I-Form Power-I / 3-back I — 3rd back behind QB **(future)**
- Maryland I — like Power-I but FB closer to QB **(future)**

### Singleback family (under-center, 1 RB)

- Singleback Ace **(have)** — 11 personnel, balanced
- Singleback Doubles — 2 WR each side **(future)**
- Singleback Trips **(future)** — 3 WR one side
- Singleback Bunch **(future)** — 3 WR clustered tight
- Singleback Big — 12 or 13 personnel **(future)**
- Trey Right **(have)** — 12 personnel, 2 TE flanking, 2 WR strong

### Shotgun family (QB ~5 yd back, HB beside)

- Shotgun Trips Right **(have)** — 11 personnel, 3 WR strong
- Shotgun 2x2 / Spread **(this batch)** — 11 personnel, balanced 2x2
- Shotgun Trips Left **(future)** — mirror of Trips Right
- Shotgun Bunch **(future)** — 3 WR clustered
- Shotgun Empty 5-wide **(future)** — 00 personnel, no RB
- Shotgun Y-Flex **(future)** — TE flexed as slot
- Shotgun Spread Option / RPO base **(future)**

### Pistol family (QB ~4 yd back, HB directly behind QB)

- Pistol **(this batch)** — 11 personnel base
- Pistol Diamond — 3 backs in pistol **(future)**
- Pistol Trips — 3 WR one side **(future)**

### Heavy / goal-line family

- Goal Line Jumbo **(have)** — 22 personnel, 2 TE in-line
- Full House **(have)** — 32 personnel, 3-back triangle
- Tank / Big Heavy — 23 personnel, 3 TE **(future)**
- Heavy I — 22 personnel I with extra TE wing **(future)**

### Empty / spread family

- Empty 10 personnel **(have)** — 1 TE + 4 WR, no RB
- Empty 00 personnel — 5 WR no TE **(future)**

### Specialty / option family

- Wildcat **(this batch)** — direct snap to RB, QB split as WR
- Wing-T **(this batch)** — classic option / misdirection 22-personnel HS staple
- Wishbone — 3-back triple-option **(future)**
- Flexbone — modern triple-option (academies) **(future)**
- Run-and-Shoot — shotgun 4-WR no TE **(future)**
- Single Wing — single-wing direct-snap throwback **(future)**
- Double Wing — youth/HS heavy 2-wing **(future)**

---

## Defensive formations (separate schema work)

Defensive formations don't have plays in the same way — they have **fronts** (DL alignment) + **coverage shells** (DB rotation). A future schema for defensive formations should support both layers.

### Fronts

- 4-3 base **(future)**
- 3-4 base **(future)**
- 4-2-5 **(future)**
- 3-3-5 **(future)**
- 46 Bear front **(future)**
- 5-2 Eagle front **(future)**
- Goal-line stand (8+ in box) **(future)**

### Personnel groupings

- Base (4-3 or 3-4) **(future)**
- Nickel (5 DBs) **(future)**
- Dime (6 DBs) **(future)**
- Quarter / Prevent (7 DBs) **(future)**

### Coverage shells

- Cover 0 (man, no help) **(future)**
- Cover 1 / Cover 1 robber **(future)**
- Cover 2 (zone) **(future)**
- Cover 2 man **(future)**
- Cover 3 **(future)**
- Cover 4 / quarters **(future)**
- Tampa 2 **(future)**
- Pattern-match variants **(future)**

---

## Play families per formation (offense)

For each formation, the staple plays we should cover. **Bold** = added in current builds; plain = future.

### I-Formation
**Power O, ISO, PA Y-Cross, Bootleg Flat, HB Screen** — Counter Trey, Lead Toss, Off-Tackle, Smash Strong, Flood

### Singleback Ace
**Inside Zone, Outside Zone, Mesh, Stick, Smash, Four Verticals** — Power, HB Draw, PA Bootleg, Y-Stick variants

### Shotgun Trips Right
RPO Bubble, Snag, Smash Trips, Flood, Levels, Y-Cross from spread, Quick Slants, Stick-Nod **(future)**

### Pistol *(this batch)*
**Inside Zone Read, Outside Zone Read, Power Read** — Veer, RPO Slant, Bootleg, Counter Read

### Shotgun 2x2 *(this batch)*
**Snag, Stick, RPO Slant** — Mesh, Curl-Flat, Smash, Hi-Lo, Drive, Crossers

### Wing-T *(this batch)*
**Buck Sweep, Belly, Trap** — Down, Jet Sweep, Boot, Waggle, Reverse, Belly Pass

### Wildcat *(this batch)*
**Power, Counter, Jet Sweep** — Sweep, Pass (RB throws), Speed Option, Reverse

### Goal Line / Big I / Full House
QB Sneak, Power O, Lead ISO, PA Tight End Corner, PA Fade, Naked Boot **(future)**

### Empty 10 personnel
Mesh, Levels, Smash, Flood, 4 Verts, Quick Slants, Hot reads, Choice routes **(future)**

### Trey Right
Flood, Smash, PA Cross, Y-Sail, Stick-Stop combos **(future)**

---

## Era / level coverage targets

Each formation should ideally have plays tagged across:

- **High school** — option-based, simple-rule plays (Buck Sweep, Belly, Power, Stretch)
- **College** — RPO-heavy, spread-based, hybrid concepts (Mesh, Snag, Inside Zone Read)
- **NFL / pro** — complex passing trees, multiple personnel, situational specialists (PA Y-Cross, Bootleg Flat, Levels)

Tags `high-school`, `college`, `nfl`, `any-level` are used per play to make this filterable.

---

## How to use this document

When adding new content:

1. Look here first to see what's missing
2. Update the status (have / this batch / next / future)
3. If the gap involves a new schema (e.g. defensive formations), call it out in plan.md, not here

When the system has solid coverage of a section, mark it with a checkmark (eventually).
