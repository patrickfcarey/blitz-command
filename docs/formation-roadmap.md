# Formation & Play Coverage Roadmap

Comprehensive list of formations and play families across HS / college / pro football, with status:

- **(have)** — file exists in `data/formations/` or `data/plays/`
- **(next)** — planned for the immediate next pass
- **(future)** — known but lower priority

When this list grows out of date, update it. Cross-reference for "what's missing."

**Last refresh:** 2026-04-30 — 54 formations / 144 plays in library.

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

- Singleback Ace **(have)** — 12 personnel, symmetric (Madden default)
- Singleback Trio **(have)** — 11 personnel, 1 TE / 3 WR with weak slot
- Singleback Doubles — 2 WR each side **(future)**
- Singleback Bunch — 3 WR clustered tight **(future)**
- Singleback Big — 13 personnel **(future)**
- Trey Right / Trey Left **(have)** — 12 personnel, 2 TE flanking + 2 WR strong

### Shotgun family (QB ~5 yd back, HB beside)

- Shotgun 2x2 **(have)** — 11 personnel, balanced 2x2
- Shotgun Trips Right / Left **(have)** — 11 personnel, 3 WR strong
- Shotgun 2x1 TE-Strong / TE-Weak **(have)** — 11 personnel asymmetric
- Shotgun 3x0 **(have)** — all 3 WR one side
- Empty **(have)** — 10 personnel, 1 TE + 4 WR
- Shotgun Bunch **(future)** — 3 WR clustered
- Empty 00 personnel — 5 WR no TE **(future)**
- Shotgun Y-Flex **(future)** — TE flexed as slot

### Pistol family (QB ~4 yd back, HB directly behind QB)

- Pistol **(have)** — 11 personnel base (Chris Ault Nevada)
- Pistol Diamond **(have)** — 20 personnel, 3 backs in diamond
- Pistol Trips **(future)** — 3 WR one side

### Heavy / goal-line family

- Goal Line Jumbo **(have)** — 22 personnel, 2 TE in-line
- Full House **(have)** — 32 personnel, 3-back triangle
- Tank / Big Heavy — 23 personnel, 3 TE **(future)**
- Heavy I — 22 personnel I with extra TE wing **(future)**

### Empty / spread family

- Empty 10 personnel **(have)** — 1 TE + 4 WR, no RB
- Empty 00 personnel — 5 WR no TE **(future)**

### Specialty / option family

- Wildcat **(have)** — direct snap to RB, QB split as WR
- Wing-T **(have)** — classic option / misdirection 21-personnel HS staple
- Wishbone **(have)** — 3-back triple-option (Texas / Oklahoma 1968-)
- Flexbone **(have)** — modern triple-option (Air Force / Navy / Georgia Tech)
- Run-and-Shoot **(have)** — shotgun 4-WR no TE (Mouse Davis / June Jones)
- Single Wing — single-wing direct-snap throwback **(future)**
- Double Wing — youth/HS heavy 2-wing **(future)**

---

## Defensive formations

Defensive formations carry **front** (DL alignment) + **coverage shell** (DB rotation) + per-defender `responsibilities` (role + aim + covers_player). The drawing tool renders zones / man-coverage lines / rush arrows from these.

### Built (9)

- **defense-4-3-cover-3** — base 4-3 front + cover 3 shell (most common base in football)
- **defense-4-3-cover-2** — base 4-3 + 2 deep
- **defense-3-4-cover-3** — 3-4 front + cover 3 (NT two-gap)
- **defense-4-2-5-cover-2** — modern nickel, 2 deep halves
- **defense-nickel-cover-1** — 5 DBs, single-high man (man-coverage situations)
- **defense-dime-cover-4** — 6 DBs, quarters (passing-down)
- **defense-46-bear-cover-0** — Bear front, zero blitz
- **defense-goal-line-6-2** — 6 DL across, short-yardage stop
- **defense-prevent-3-2-6** — end-of-half cover-4 deep

### Future

- 3-3-5 stack
- 4-3 cover-1
- Tampa 2 standalone
- Blitz packages (zero blitz, fire zone, double-A)

---

## Play families per formation (offense)

For each formation, the staple plays. **Bold** = built; plain = future. The library currently has **144 plays** across these formations — count via `find_plays_by_formation()` for the live total.

### I-Formation
**Power O, ISO, Counter Trey, Lead Toss, PA Y-Cross, Bootleg Flat, HB Screen, Veer Option** — Off-Tackle, Smash Strong, Flood

### Singleback Ace
**Inside Zone, Power O** — PA Cross, Bootleg, Y-Stick variants

### Singleback Trio
**Inside Zone, Outside Zone, Power, HB Draw, Mesh, Smash, Stick, Four Verticals, PA Cross** — RPO variants, Screen

### Shotgun 2x2
**Snag, Stick, Jet Sweep, RPO Slant, Power Read, QB Counter, QB Power** — Mesh, Smash, Curl-Flat

### Shotgun Trips Right / Left
**Flood, Snag, RPO Bubble, Counter Read** — Smash Trips, Levels, Y-Cross, Stick-Nod, Quick Slants

### Trey Right / Left
**Flood, Smash, PA Cross** — Y-Sail, Stick-Stop combos

### Pistol
**Inside Zone Read, Outside Zone Read, RPO Bubble, Bootleg, Zone Read + Slant RPO** — RPO Slant, Counter Read

### Pistol Diamond
**Split Zone, Power Read** — Lead Draw, Counter

### Wing-T
**Buck Sweep, Belly, Trap, Reverse, Waggle** — Down, Jet Sweep, Boot, Belly Pass

### Wildcat
**Power, Counter, Sweep, Jet Sweep, Speed Option** — Pass (RB throws), Reverse

### Wishbone
**Triple Option, FB Dive, Waggle** — Counter Option, Sprint Pass

### Flexbone
**Triple Option Veer, Midline Triple, PA Bootleg** — Counter Option, Power Pitch, Jet Sweep

### Run-and-Shoot
**Choice, Switch Verticals** — Smash-with-Choice, Mesh, 4-Verts (choice form), Slant-and-Go

### Goal Line / Big I / Full House
**QB Sneak, Power, PA Tight End Corner** — Lead ISO, PA Fade, Naked Boot, FB Dive (Full House)

### Empty 10 personnel
**Mesh, Four Verticals** — Levels, Smash, Flood, Quick Slants, Hot reads, Choice routes

### I-Formation Twins Weak
**Mesh, Stick** — Quick-game variants from a power formation

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
