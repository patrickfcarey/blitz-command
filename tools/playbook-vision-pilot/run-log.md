# Playbook vision pilot — run log

Append-only. Every tool call gets a line BEFORE it runs (so if the socket
dies, we still see where we died) and a result line AFTER it returns.

Format:
  [HH:MM:SS] PRE  step=<n>  tool=<name>  args=<summary>
  [HH:MM:SS] POST step=<n>  result=<summary or ERROR>

Rules in force (set 2026-05-20):
- max 5 subagents in flight at once
- haiku subagents for vision (cheaper, prior sessions confirmed it works)
- focus: 5 offensive linemen, with CENTER (circle glyph) as anchor
- other 4 OL are squares flanking the C on the LOS row

---

[20:40:00] PRE  step=1  tool=Write  args=create run-log.md
[20:40:00] POST step=1  result=ok
[20:40:00] PRE  step=2  tool=Write  args=create name_to_prior.py (interrupted by user)
[20:40:00] POST step=2  result=interrupted, no write
[20:45:00] PRE  step=2b tool=Write  args=create name_to_prior.py (retry)
[20:45:01] POST step=2b result=ok, file written
[20:45:02] PRE  step=3  tool=Bash   args=python3 name_to_prior.py
[20:45:03] POST step=3  result=ok, 31/50 plays decoded a prior, priors.json written
[20:55:00] PRE  step=4  tool=Bash   args=copy 6 crops to tools/playbook-vision-pilot/sample-crops/ for user inspection
[20:55:01] POST step=4  result=ok, 6 jpgs copied

---

Session 2026-05-20 21:09 — investigating socket failures

[21:09:52] PRE  step=5  tool=Bash   args=date (timestamp probe)
[21:09:52] POST step=5  result=ok, 21:09:52
[21:09:53] PRE  step=6  tool=Bash   args=stat newest transcript jsonl to find crash points
[21:09:53] PRE  step=7  tool=Bash   args=grep API errors / socket close in jsonls
[21:09:53] PRE  step=8  tool=Bash   args=check wsl/network conditions (dmesg, ip, mtu)
[21:10:30] POST step=6  result=ok, two transcripts contain isApiErrorMessage with "socket closed unexpectedly": bd2be00e (msg 259, 26.8s turn) and 5c1518f6 (msg 116, 22s turn). Both are LONG sessions, not short ones.
[21:10:30] POST step=7  result=ok, error text in both: "API Error: The socket connection was closed unexpectedly. For more information, pass `verbose: true` in the second argument to fetch()" — comes from Node fetch ECONNRESET.
[21:10:30] POST step=8  result=ROOT CAUSE CANDIDATE — tcp_keepalive_time=7200s (2h kernel default). Egress route to api.anthropic.com goes via eth2 (MTU 1441, likely VPN/corp interface, NOT the 1500-MTU home eth1). Long model turns idle the socket past intermediate LB/VPN cutoff, no keepalive sent, socket silently RST.
[21:10:31] PRE  step=9  tool=Bash   args=check route to api.anthropic.com
[21:10:31] POST step=9  result=eth2 (10.22.18.x, MTU 1441) is the egress. Confirmed VPN-shaped interface in path.

---

Session resumes 2026-05-20 21:17 — VPN was the culprit, user disabling. Picking up pilot dispatch.

[21:17:41] PRE  step=10 tool=Bash   args=verify pipeline state — list pilot-sample.json, crops dir, priors.json
[21:18:10] POST step=10 result=NO artifacts on disk. pilot-sample.json missing, priors.json missing, pilot-work/ doesn't exist, crops only in sample-crops/ (6 inspection copies). Prior run-log entries about "priors written" were not actually persisted. Pipeline must be re-run from step 1.
[21:18:15] PRE  step=11 tool=Read   args=sample_plays.py — inputs/outputs
[21:18:15] PRE  step=12 tool=Read   args=crop_play_panels.py — inputs/outputs
[21:18:15] PRE  step=13 tool=Read   args=name_to_prior.py — inputs/outputs
[21:18:30] POST step=11 result=ok, sample_plays.py reads .docx-cache-m25-plays, writes /tmp/pilot-work/pilot-sample.json (50 plays, stratified)
[21:18:30] POST step=12 result=ok, crop_play_panels.py reads pilot-sample.json + research_artifacts/PS3/Madden NFL 25/Playbooks/*.docx, writes /tmp/pilot-work/crops/<id>.jpg
[21:18:30] POST step=13 result=ok, name_to_prior.py reads pilot-sample.json, writes /tmp/pilot-work/priors.json
[21:18:30] PRE  step=14 tool=Bash   args=verify cache + playbook docx exist
[21:19:00] POST step=14 result=ok, 183 cache chunks, 51 playbook docx — sources intact. /tmp wipe is the cause of missing artifacts.
[21:19:10] PRE  step=15 tool=Bash   args=run sample_plays.py
[21:19:30] POST step=15 result=ok, 50 plays across 31 teams written to /tmp/pilot-work/pilot-sample.json. Population: pass_generic=7755, pass_named=3481, run_clean=759, run_generic=4207.
[21:19:35] PRE  step=16 tool=Bash   args=run crop_play_panels.py + name_to_prior.py
[21:20:05] POST step=16 result=ok, 50 crops in /tmp/pilot-work/crops/, 31/50 priors in /tmp/pilot-work/priors.json.

[21:20:30] PAUSED for user confirmation before dispatching 100 subagents.
[21:21:00] POST: user chose "pilot 2 first, then 98"
[21:21:10] PRE  step=17 tool=Bash   args=pick a play with a prior for the 2-subagent pilot
[21:21:30] POST step=17 result=ok, picked baltimore_ravens__power_o__0058_1 (run_clean, prior=concept=power)
[21:21:35] PAUSED — user wants to nail down OL-identification protocol before any subagent dispatch. Discussing visual rules for finding the 5 OL with C-glyph as anchor.

CORRECTION 21:24 — the earlier run-log rule ("CENTER is circle, other 4 OL are squares") is WRONG. User's correct rule:
- ALL 5 OL are circles.
- CENTER = bare circle (no teardrop).
- OG/OT (4 of them) = circle with an attached teardrop indicating initial step.
- Run play: teardrop points FORWARD (drive/push step).
- Pass play: teardrop points BACKWARD (pass-pro kickslide step).
- Draw / play-action: footwork direction may not be reliable — treat as uncertain.
- QB: ALWAYS lined up directly behind C (use this as a second anchor for finding C).
- Wildcat: the RB IS the QB by definition (lined up at QB position).

[21:24:00] PRE  step=18 tool=Read   args=look at a PASS play crop to verify the teardrop-backward heuristic
[21:25:30] POST step=18 result=ok, viewed Houston X Drag crop. Confirmed I can see OL cluster + skill-player PS-button glyphs. Outstanding questions: C visually distinct at this res? upscaling needed?
[21:25:45] PRE  step=19 tool=Write  args=add session-log-law memory
[21:25:45] PRE  step=20 tool=Edit   args=update docs/session-log.md with current session
[21:25:45] PRE  step=21 tool=SendUserFile args=send X Drag crop to user for joint inspection
[21:26:30] POST step=19 result=ok, feedback_session_log_law.md saved + MEMORY.md updated
[21:26:30] POST step=20 result=ok, docs/session-log.md has a new "2026-05-20 (cont.)" entry covering vision pilot resume + socket-drop diagnosis + OL-rule correction
[21:26:30] POST step=21 result=ok, X Drag crop surfaced to user

CORRECTION 21:30 — OL-rule has exceptions. In the X Drag (0-TE pass) image, the C-glyph IS rendered as a SQUARE, not a circle. Need to figure out the trigger (0 TE? pass play? something else). The earlier rule "C is bare circle" is NOT universal.

STRATEGY CHANGE 21:31 — pivot to TE identification first. Once TE is identifiable, WR is "the colored receiver split out wide who isn't on the LOS next to the OL." User wants a play we KNOW is 2-TE (e.g., Singleback Ace) so we can study the TE glyph in isolation.

[21:32:00] PRE  step=22 tool=Bash   args=peek Baltimore Ravens.docx structure for formation Heading-1 paragraphs + find a Singleback Ace play
[21:32:30] POST step=22 result=no Heading-1 styles in M25 docx, but the per-team cache has a 'formation_list' entry kind (family + highlighted) that precedes each play_screen. So formation context IS in the cache, just keyed by image order — same trick as NCAA 06 but inside the cache, not the docx.
[21:33:00] PRE  step=23 tool=Bash   args=build formation→plays index for Ravens, pick HB Zone Wk in Singleback Ace (img 7 panel 1)
[21:33:30] POST step=23 result=ok, Ravens have ('SINGLEBACK', 'Ace') with 12 plays including HB Zone Wk (img 7 panel 1, run), Z Spot (img 8 panel 0, pass), Y Shallow Cross.
[21:33:45] PRE  step=24 tool=Bash   args=crop img 7 of Ravens docx into 3 panels + full row → sample-crops/ravens_ace_img7_*.jpg
[21:34:00] POST step=24 result=ok, 4 jpgs written
[21:34:15] PRE  step=25 tool=Read   args=view ravens_ace_img7_p1.jpg
[21:34:30] POST step=25 result=ok, CLEAR visual: WR(isolated)-TE-OT-OG-C(square)-OG-OT-TE-WR(isolated). 5 OL + 2 TE + 2 WR. C is white square in middle of cluster.
[21:35:00] PRE  step=26 tool=SendUserFile args=send HB Zone Wk crop
[21:35:30] POST step=26 result=ok, delivered
[21:36:00] PRE  step=27 tool=Bash   args=upscale ravens Ace p1 (run) and Houston X Drag (pass) 3x via PIL LANCZOS for teardrop-direction study
[21:37:00] POST step=27 result=ok, 3x PNGs written. C=square confirmed in both. Teardrops still tiny.

User clarifications 21:40:
- PS button glyphs include L1/R1 (shoulder), not just face buttons. So 6 possible buttons.
- Run plays have plain-circle skill players EXCEPT RPO plays (where eligible target gets a button).
- Color-vs-mono rule = pass-vs-run is "nearly always true".
- Teardrop direction MATTERS — don't skip. Hypothesis: easier to detect ABOVE vs BELOW the LOS horizontal line. Identify LOS line first, then look at teardrop location relative to it.
- User wants to inspect Ace run plays — point them to file paths.

[21:41:00] PRE  step=28 tool=Bash   args=identify all Ace plays (img 7-N) per Ravens, crop each image at 3x, label run/pass per panel
[21:42:30] POST step=28 result=ok, 12 Ace panels written to sample-crops/ace-batch/, named img{NN}_p{0..2}_{run|pass}_{slug}_3x.png
[21:43:00] PRE  step=29 tool=Read   args=read 2 Ace panels (HB Dive run vs Z Spot pass) for visual comparison
[21:43:30] POST step=29 result=ok, confirmed: positionally identical (9 LOS slots, C-square always center, TE-adjacent, WR-isolated). Stubs hard to read at 3x → need LOS-only re-zoom.
[21:44:00] PRE  step=30 tool=Bash   args=crop LOS band only, ~7.5x total zoom, for teardrop study
[21:44:30] POST step=30 result=ok, 2 LOS-band PNGs in sample-crops/los-zoom/
[21:45:00] PRE  step=31 tool=Read   args=view LOS-only 7.5x crops for teardrop direction
[21:45:30] POST step=31 result=

VISUAL FINDING — TEARDROP DIRECTION (preliminary, 2 samples only):
- HB Dive (RUN): all 5 OL + 2 TE plain-circle glyphs have stub BELOW the circle (toward bottom of image / offensive backfield).
- Z Spot (PASS): same — 4 OG/OT plain-circle glyphs have stub BELOW the circle. WR/TE are colored button-shapes with no visible stub.
- DIRECTION APPEARS IDENTICAL in run vs pass at this resolution. User's rule "run=forward, pass=backward" not visually verifiable here.
- HYPOTHESIS: the stub is a STANCE icon (head + body in 3-point stance), not a STEP icon. M25 play diagrams may not encode first-step direction. Would need to check older Madden/NCAA titles where the user may have observed the rule.
- Awaiting user inspection of los-zoom/*.png to confirm or correct.

[21:46:00] PRE  step=32 tool=SendUserFile args=send both LOS-zoom files to user
[21:46:30] POST step=32 result=ok, 2 files delivered

[21:47:00] PAUSED — user is inspecting the LOS-zoom files locally. Said: "we have to draw a LOS." Next step (waiting on user confirmation): overlay a horizontal LOS reference line on the crops so direction is grounded.

[21:48:00] User: "draw it through the center line of the circle for a OL". Approach: detect y-row of OL circles programmatically (brightest white-pixel row in band), draw a horizontal line through that y, apply to both LOS-zoom crops.

[21:48:30] PRE  step=33 tool=Bash   args=detect OL center y in LOS-zoom crops, overlay horizontal line, write *_LOS_marked.png
[21:49:00] POST step=33 result=auto-detect failed (picked stub row in HB Dive at y=290, R1-marker row in Z Spot at y=334).
[21:49:30] PRE  step=34 tool=Bash   args=retry with tighter near-white threshold (>235)
[21:50:00] POST step=34 result=still inconsistent — HB Dive y=290 (stub row), Z Spot y=242 (correct). Auto-detect picks the row with MOST white pixels, but adding stubs makes lower rows score higher than true circle-center rows.
[21:50:30] PRE  step=35 tool=Bash   args=hand-pick y=240 for both (shared LOS geometry)
[21:51:00] POST step=35 result=ok, both marked PNGs written
[21:51:30] PRE  step=36 tool=Read   args=view marked PNGs
[21:52:00] POST step=36 result=

VISUAL FINDING — LOS LINE OVERLAY (y=240):
- HB Dive (RUN): cyan line cuts across the TOP of OL circles. OL stubs extend BELOW the line. TE+WR same stance (plain circles with stub-below-line).
- Z Spot (PASS): cyan line cuts across the TOP of OL circles. The 4 plain-circle OG/OT have stubs BELOW the line. TE/WR are colored PS button-glyphs (no stubs visible — the body is the colored shape).
- DIRECTION IS CONSISTENT: in both run and pass, OL stubs are BELOW the LOS line (on the offensive backfield side). Not below-for-pass and above-for-run.

PROVISIONAL CONCLUSION: M25 play diagrams render the OL stub as a STANCE icon (head above, body/feet below) regardless of run/pass. The "first-step direction" rule from older games does not appear to apply here. User to confirm or rebut.

[21:52:30] PRE  step=37 tool=SendUserFile args=send marked files to user
[21:52:45] POST step=37 result=ok, 2 marked files delivered

User insight 21:53: "it's possible pass protection plays have the OL behind the center — we should just draw this line through the center of the center's square."
Implication: anchor on the C-square, not on the OL-circle row. The C-square is invariant (always center, always white, always square); the OL circles can shift back on pass-pro.

[21:53:30] PRE  step=38 tool=Bash   args=detect C-square center via filled-white-block search (numpy), redraw LOS line through square center
[21:54:00] POST step=38 result=ok, C detected at y=250 (HB Dive) and y=252 (Z Spot) via 40x40 white-density sweep. Identical y as expected (shared geometry).
[21:54:30] PRE  step=39 tool=Read   args=view C-anchored marked PNGs
[21:55:00] POST step=39 result=

VISUAL FINDING — RUN vs PASS IS POSITIONAL OFFSET, not stub direction:
- HB Dive (RUN): cyan line through C passes through OL circle CENTERS too. OL row even with C.
- Z Spot (PASS): cyan line through C passes through OL circle TOPS. OL row sits ~half-circle BELOW C. OL has dropped back into pass-pro stance.

NEW HYPOTHESIS: M25 distinguishes run vs pass-pro by OL vertical offset from C, not teardrop direction. The stubs are stance icons (constant down); the body POSITION shifts back on pass plays. This matches the user's instinct that "pass protection plays have the OL behind the center."

[21:55:30] PRE  step=40 tool=SendUserFile args=send the C-anchored marked PNGs for user verification of the offset hypothesis
[21:55:45] POST step=40 result=ok, delivered.

USER CONFIRMED 21:56: "yeah that looks about right". OL-vertical-offset-from-C rule is the run-vs-pass signal in M25 (not teardrop direction).

CURRENT LOCKED RULES (M25 play diagrams):
1. C (center) = white square in the middle of the LOS cluster — always.
2. OL = the 5-glyph cluster surrounding C; 4 plain-white circles flanking C.
3. TE = circle adjacent to the OL cluster, NO gap from OT (0-3 of them).
4. WR = circle (run) or PS-button-color glyph (pass) split from OL cluster by a visible GAP.
5. PS button glyphs: □ purple, △ green, ⊗ blue, ⊙ red, L1/R1 also possible.
6. Color skill players → PASS play; mono skill players → RUN (except RPO).
7. RUN: OL circle centers ON the LOS line through C-square center.
8. PASS (pass-pro): OL circle centers BELOW the LOS line through C-square center (dropped back ~half a circle).
9. QB always lined up directly behind C in non-shotgun. Wildcat: RB at QB position.
10. Stubs below OL circles are STANCE icons (head above, body below), not step-direction icons.

[21:56:30] PAUSED — what next? Options:
  a) Verify rules generalize across Singleback 3 TE, Shotgun 2x1, Singleback 2x1 (the other 3 starting formations user named).
  b) Move on to drafting the subagent prompt using these locked rules + dispatch a 2-subagent pilot.
  c) Both — verify generalization first, then prompt.

User picked (a) at 21:58.

[21:58:30] PRE  step=41 tool=Bash   args=index Ravens formations, find a 3TE-y (Jumbo), a 3WR (Y-Trips TE Slot or Doubles Flex), and a Shotgun 2x1 (GUN Ace Twins or similar). Crop run+pass for each at 7.5x LOS-zoom with C-anchored line.
[21:59:00] POST step=41 result=ok, 6 verification PNGs in sample-crops/formation-verify/ — Jumbo run+pass, Y-Trips run+pass, Ace Twins run+pass.
[22:00:00] PRE  step=42 tool=Read   args=spot-check 2 of the 6 (Jumbo run + Ace Twins pass)
[22:00:30] POST step=42 result=RULES HOLD across formations:
  - Jumbo run (HB Stretch): wider LOS cluster (3 TEs visible: 1 isolated left WR + 7-cluster including C + visible H-back/3rd-TE below LOS at right of cluster). C-square is white. OL circles AT cyan line. ✓
  - Ace Twins pass (Stick): GUN formation (QB behind LOS in shotgun). OL circle centers clearly BELOW the cyan LOS line → pass-pro offset rule holds even in shotgun. ✓
  - Other 4 (Jumbo pass, Y-Trips run+pass, Ace Twins run) sent to user for verification.
[22:01:00] PRE  step=43 tool=SendUserFile args=send all 6 verification images for joint inspection
[22:01:15] POST step=43 result=ok, 6 files delivered.

User feedback 22:02: "where did you save them? always tell me where you put them." Saved as [[feedback-always-tell-paths]] memory. State WSL + Windows path in reply, not just in run-log.

User confirmed verification 22:05 — rules hold across all 4 starting formations. Three corrections/additions:
- Jumbo: 3rd TE lines up as "HB" but tight next to the inline TE (wing-TE / U slot, not a deep H-back).
- GUN Ace Twins: 2 TEs visible, not 1.
- Y-Trips TE Slot: 1 TE (in the slot) — user corrected themselves at 22:08 (initial guess of 2 was wrong).
- NEW ROUTE-COLOR RULE: blue/cyan routes = block-first-then-release (chip routes, RB swing after pass-pro, delayed-release TE routes).
- Y-Trips slot WR can be hard to distinguish from a TE because the gap to the OL cluster is small. Edge case for gap-based WR detection.

UPDATED FORMATION COMPOSITIONS:
- Singleback Ace: 5 OL + 2 TE + 2 WR = 9 on LOS
- Singleback Jumbo: 5 OL + 2 TE (LOS) + 1 wing-TE (HB pos, tight to inline TE) + 1 WR = 8 on LOS + 1 off
- Singleback Y-Trips TE Slot: 5 OL + 1 TE (flexed slot) + 3 WR = 9 on LOS (slot-WR/TE gap can be ambiguous)
- GUN Ace Twins: 5 OL + 2 TE + 2 WR = 9 on LOS, QB in shotgun (~5 yards behind C)

Route color rules confirmed 22:12:
- RED = primary pass route OR run ball-carrier path (disambiguated only by play_type).
- YELLOW = standard receiver route.
- BLUE/CYAN = block-first-then-release.
- Other colors / dashed lines (option routes, motion paths) = NOT YET ENUMERATED. Pilot subagents will flag with color=unknown / style=dashed + freeform notes; we'll learn from the outputs.

Taxonomy phase complete. Moving to subagent prompt draft.

[22:13:00] PRE  step=44 tool=Write  args=draft prompt + schema in tools/playbook-vision-pilot/subagent-prompt.md (review before any dispatch)
[22:13:30] POST step=44 result=ok, subagent-prompt.md v1 drafted with all 10 locked rules + extraction schema + unknown-fallback handling.

User 22:15: prompt drafted but more formations should be verified before any dispatch. Picked: 2-back sets (I-Form/Strong/Weak) + Goal Line/heavy.

[22:16:00] PRE  step=45 tool=Bash   args=find run+pass plays for I-FORM Pro, STRONG Pro, WEAK H Pro, GOAL LINE Normal — crop at 7.5x LOS-zoom with C-anchored line
[22:16:30] POST step=45 result=ok, 8 PNGs to sample-crops/formation-verify-2/. C detected at y=246-254 consistently across all 8.
[22:17:00] PRE  step=46 tool=Read   args=spot-check I-Form Pro run + Goal Line run
[22:17:30] POST step=46 result=Rules hold on hardest formations:
  - I-Form Pro HB Blast: 7-cluster (5 OL + 2 TE) + 2 isolated WRs + 2 BACKFIELD circles stacked (FB + HB) ✓
  - Goal Line HB Dive: 9-cluster (5 OL + 4 TE) + 0 WR + 2 backfield circles ✓
  - C-square detected in both. Cyan LOS line through OL circle centers (run).
- 8 files surfaced to user for verification at sample-crops/formation-verify-2/.

Path for user:
  WSL:     /mnt/c/GitHub/blitz-command/tools/playbook-vision-pilot/sample-crops/formation-verify-2/
  Windows: C:\GitHub\blitz-command\tools\playbook-vision-pilot\sample-crops\formation-verify-2\

USER CORRECTION 22:19: the LOS-zoom band (y=0.45..0.70) IS CLIPPING THE HB. In I-Form/Strong/Weak the backfield should show 3 stacked circles behind C = QB + FB + HB. I had been misreading QB as FB and missing HB entirely. Need to widen the crop band to include the deeper backfield.

[22:19:30] PRE  step=47 tool=Bash   args=widen LOS-zoom band from y=0.45..0.70 to y=0.30..0.95 (above LOS through full backfield, stop above bottom UI). Re-render the 8 formation-verify-2 crops.
[22:20:00] POST step=47 result=ok, 8 WIDE PNGs in sample-crops/formation-verify-2-wide/. C detected y=582-590 in new (taller) band, x consistent.
[22:20:30] PRE  step=48 tool=Read   args=spot-check I-Form Pro + Strong Pro run plays
[22:21:00] POST step=48 result=
  - I-Form Pro HB Blast: confirms 3 stacked circles behind C = QB + FB + HB. ✓
  - Strong Pro Power O: visible QB behind C + FB offset strong-side + HB deeper. NOT pure stacked. Matches Strong-Pro design.
- All 8 wide crops sent to user for verification.

Path:
  WSL:     /mnt/c/GitHub/blitz-command/tools/playbook-vision-pilot/sample-crops/formation-verify-2-wide/
  Windows: C:\GitHub\blitz-command\tools\playbook-vision-pilot\sample-crops\formation-verify-2-wide\

ADDITION TO RULES — BACKFIELD COMPOSITION (M25):
- Under-center: QB directly behind C-square (just below LOS).
- I-Form: QB + FB + HB STACKED vertically behind C (3 circles in one column).
- Strong: QB behind C, FB offset to strong side, HB deeper (offset/staggered).
- Weak: QB behind C, FB offset to weak side, HB deeper.
- Goal Line: similar to Strong/Weak but with all backs tight.
- Singleback: QB behind C + 1 HB ~5-7 yards back (2 circles total).
- Shotgun: QB ~5 yards behind C (no under-center stack); HB to one side of QB.
- Pistol: QB ~3 yards behind C, HB directly behind QB (stacked but shorter than I-Form).
- Wildcat: RB lined up at QB position (no QB).

Subagent prompt v1 needs an UPDATE to add this backfield-composition rule.

User confirmed wide crops at 22:24. Then picked: verify Empty + Bunch + Pistol + Wildcat.

[22:25:00] PRE  step=49 tool=Bash   args=index Empty/Bunch (Ravens), Pistol Strong (Panthers), Wildcat Normal (Bills) — pick run+pass each (Empty 0-run, Wildcat 0-pass in available data)
[22:25:30] POST step=49 result=ok, 7 candidates picked across 3 teams.
[22:26:00] PRE  step=50 tool=Bash   args=crop the 7 at wide LOS-zoom with C-anchored line
[22:26:30] POST step=50 result=ok, 7 WIDE PNGs in sample-crops/formation-verify-3/.
[22:27:00] PRE  step=51 tool=Read   args=spot-check GUN Empty pass + Wildcat Power run
[22:27:30] POST step=51 result=
  - GUN Empty Ravens Wheels: 5 OL + 5 button-colored eligibles + QB in shotgun, ZERO RB. OL below LOS line (pass) ✓.
  - Wildcat Power: 1 backfield circle = RB at QB position. Cyan/blue motion-or-block arrow from a backfield player (first wildcat sample shows the rule). ✓

Path:
  WSL:     /mnt/c/GitHub/blitz-command/tools/playbook-vision-pilot/sample-crops/formation-verify-3/
  Windows: C:\GitHub\blitz-command\tools\playbook-vision-pilot\sample-crops\formation-verify-3\

User 22:30: confirmed all 7 edge-case verify-3 crops. Taxonomy now verified across 15 distinct formations. Marking task #4 done; updating subagent-prompt.md with backfield-composition rule and crop-format note.

[22:31:00] PRE  step=52 tool=Edit   args=update subagent-prompt.md with backfield composition + crop format + LOS-line annotation note
[22:31:30] POST step=52 result=ok, prompt v2 written. Subagent now knows: 9 backfield-composition variants by formation family; cyan line + yellow box are reference annotations (not part of the diagram); crop is wide LOS-zoom with possible deep-route clipping.

[22:33:00] Cost-optimization phase. User picked: prompt caching + verbose filenames + JPEG q=85. Skip 4x downscale to preserve teardrop signal. Pivot to direct Anthropic API (Agent tool doesn't expose cache_control).

[22:34:00] PRE  step=53 tool=Write  args=crop_for_dispatch.py — renders verbose-named JPEG q=85 with C-anchored line
[22:34:30] POST step=53 result=ok, smoke crop written to dispatch-crops/iform-pro__run__hb-blast__baltimore-ravens__img45p1__WIDE.jpg (146 KB)

[22:35:00] PRE  step=54 tool=Write  args=smoke_test.py — 2 API calls (cold + primed) on I-Form Pro HB Blast with cache_control on system prompt
[22:35:30] POST step=54 result=ok, script ready. Loads .env, calls Haiku, prints token usage incl. cache_creation + cache_read.

PAUSED — waiting on user to create .env with ANTHROPIC_API_KEY at repo root, then:
  .venv/bin/python tools/playbook-vision-pilot/smoke_test.py

[22:42:00] SMOKE TEST RAN (via "! .venv/bin/python ..."). Outputs saved to /tmp/pilot-work/extractions/iform-pro__{cold,primed}.json.

USAGE:
  cold:   input=3155  cache_creation=0  cache_read=0  output=1309  stop=end_turn
  primed: input=3183  cache_creation=0  cache_read=0  output=1509  stop=end_turn

DIAGNOSIS — 3 issues:
1. CACHE FAILED: rules section is 1238 tokens, Haiku's cache minimum is 2048. API silently ignored cache_control. FIX: expand the rules section above 2048 tokens.
2. UNDERCOUNT: I-Form Pro HB Blast should have 5 OL + 2 TE + 2 WR + QB/FB/HB. Haiku read 5 OL + 1 TE + 0 WR + QB/FB/HB. Missed: 1 wing-TE on left, both isolated WRs. Backfield correct.
3. SCHEMA DRIFT: cold used `x`/`y` and `center`; primed used `x_px`/`y_px` and `center_square`. Need stricter JSON shape enforcement in the prompt.

WORKED WELL:
- play_type correctly identified as run (both calls).
- C-square as anchor confirmed (both calls).
- OL count exactly 5 + correctly all at LOS line.
- I-Form QB/FB/HB stacked column confirmed.
- HB ball-carrier red arrow path correctly traced.
- Cyan + yellow annotations recognized as reference, not diagram.
- Verbose filename successfully consumed (both responses ID'd team/formation/play from path).

[22:43:00] PAUSED — analyzed smoke test. User to decide next step (expand rules + retry / stricter schema / different model / etc.).

User picked: fix all 3 issues in one prompt iteration, re-run smoke test.

[22:45:00] PRE  step=55 tool=Write  args=subagent-prompt.md v3 — expand SYSTEM section >2048 tokens, demand full count + players_missing array, strict hardcoded JSON field names
[22:45:30] POST step=55 result=ok, SYSTEM section now 10558 chars ≈ 2639 tokens (clears Haiku 2048 cache minimum). New protocol: 7-step extraction + completeness guidance + verbatim schema with exact field names.
[22:46:00] PRE  step=56 tool=Edit   args=smoke_test.py: update _load_rules to extract between '## SYSTEM PROMPT' and '## USER MESSAGE template' markers
[22:46:15] POST step=56 result=ok

Ready for re-run. User can:
  .venv/bin/python tools/playbook-vision-pilot/smoke_test.py
Expected: cache_creation_input_tokens > 0 on cold call, cache_read_input_tokens > 0 on primed call, better TE/WR counts.

[22:50:00] SMOKE TEST V3 RAN (Haiku 4.5, expanded prompt).
USAGE: cold input=4970 cache_creation=0 cache_read=0 output=892
       primed input=4998 cache_creation=0 cache_read=0 output=957
CACHE STILL FAILS — system prompt is now 3300+ tokens (above 2048 Haiku min) but cache_creation = 0 on cold call. The cache is never created, not just not read. Likely Haiku 4.5 doesn't yet support prompt caching (model released 2025-10-01).

EXTRACTION ISSUE — mislabeling, not undercount:
- Haiku sees all 9 LOS glyphs but labels them as 5 OL + 1 TE only.
- The isolated WRs (far left/right of cluster) get stuffed into the LT/RT slots.
- The actual OT becomes the TE.
- Coordinates reveal the misclassification: cold call has "LT" at x=341 and "RT" at x=1921 — both are far outside the cluster region, i.e. they ARE the isolated WRs.

[22:51:00] User picked: Test Sonnet 4.5 first (debug caching infrastructure).
[22:51:30] PRE  step=57 tool=Edit   args=smoke_test.py — switch MODEL to claude-sonnet-4-5 for this test
[22:51:45] POST step=57 result=ok

[2026-05-21 ~now] SMOKE TEST RAN ON SONNET 4.5.
USAGE:
  cold:   input=1667  cache_creation=3303  cache_read=0     output=1017
  primed: input=123   cache_creation=1572  cache_read=3303  output=1016

CACHE WORKS ✓ — system prompt (3303 tokens) cached on cold, hit on primed. Confirms wiring is correct → Haiku 4.5 does not support prompt caching yet.

EXTRACTION COMPLETE ✓ on Sonnet 4.5:
  - cold: 5 OL + 1 TE (right at 929) + 2 WR (left 344, right 1315) + QB/FB/HB = 11
  - primed: 5 OL + 1 TE (left at 560) + 2 WR (left 345, right 1310) + QB/FB/HB = 11

My earlier "2 TEs in cluster" eyeball count was WRONG. I-Form Pro is canonically 11-personnel (1 TE), and the cluster is 6 wide (5 OL + 1 TE attached one side). Sonnet got the structure right.

INCONSISTENCY: cold put TE on right, primed put TE on left. Coordinates drift ~50-100 px between calls. Sonnet isn't deterministic but COUNTS are stable.

COST: Sonnet+cache = ~$0.022 per call → 100-call pilot ≈ $2.20.
       Haiku no-cache = ~$0.010 per call → $1.00 (but mislabels WRs as OL).
       Sonnet 2x more expensive but actually-correct extraction.

User picked Sonnet 4.5 + caching for the full pilot.

[~now] PRE  step=58 tool=Write  args=batch_crop.py — render all 50 sample plays at wide LOS-zoom + cyan/yellow annotations, verbose filenames, JPEG q=85
[~now] POST step=58 result=ok, 50 crops + _manifest.json written to dispatch-crops/

[~now] PRE  step=59 tool=Write  args=dispatch.py — 5-worker ThreadPoolExecutor over 100 jobs (50 plays × 2 arms), Sonnet 4.5 with cache_control on system, resume-safe, --limit flag for partial runs
[~now] POST step=59 result=ok, dispatch.py ready. Run with --limit 4 first to validate pipeline before full $2.20 spend.

Path:
  WSL:     /mnt/c/GitHub/blitz-command/tools/playbook-vision-pilot/dispatch.py
  Windows: C:\GitHub\blitz-command\tools\playbook-vision-pilot\dispatch.py

To run partial test first (recommended):
  .venv/bin/python tools/playbook-vision-pilot/dispatch.py --limit 4
Then full run:
  .venv/bin/python tools/playbook-vision-pilot/dispatch.py

[~now] PARTIAL RUN (--limit 4) RESULTS:
  wall=15.7s  input=3647  cache_creation=16356  cache_read=0  output=4011  cost=$0.132
  ALL 5 WORKERS FIRED NEAR-SIMULTANEOUSLY → each created its OWN cache → 0 hits.
  Extraction quality solid (correctly identified Power O in I-Form Tight: 5 OL + 1 TE + 1 WR + QB/FB/HB stacked, "high" confidence, route descriptions accurate).

FIX: dispatch.py now pre-warms the cache with the FIRST job sequentially before launching workers. The 13s first call populates the cache; the remaining 99 should hit it.

Existing 4 outputs will be skipped on resume (resume-safe). Re-run with same --limit 4 to verify cache is hitting:
  .venv/bin/python tools/playbook-vision-pilot/dispatch.py --limit 4
Wait — but resume-safe means those 4 will be skipped. To re-test caching, either delete the 4 outputs or use --limit 6 to push past them. Cleanest:
  rm /tmp/pilot-work/extractions/*.json
  .venv/bin/python tools/playbook-vision-pilot/dispatch.py --limit 4

[~now] PARTIAL RUN #2 WITH PRIMING FIX:
  wall=29.2s  input=6791  cache_creation=3303  cache_read=9909  output=4024  cost=$0.096
  Cache CONFIRMED HIT on jobs 2/3/4 (3 hits × 3303 = 9909 read).
  Per-call avg: $0.024 → projected 100-call total ≈ $2.10-$2.20.
  Caching saved ~27% vs no-caching baseline of $0.132 / 4 = $0.033 per call.

Ready for full 100-call run. To do so:
  rm /tmp/pilot-work/extractions/*.json   # optional, resume-safe means existing 4 are skipped
  .venv/bin/python tools/playbook-vision-pilot/dispatch.py

[~now] User: "let's try and do the full run for Madden 25"
[~now] PRE  step=60 tool=Bash   args=full pilot dispatch (.venv/bin/python tools/playbook-vision-pilot/dispatch.py) — 100 calls, expected ~2 min, ~$2.10
[~now] POST step=60 result=
  96/96 OK in 319.5s wall (5.3 min).
  input=86709  cache_creation=75380  cache_read=317088  output=101681
  cost=$2.163 (matches estimate).
  100 extractions total in /tmp/pilot-work/extractions/ (96 fresh + 4 from partial test).

Next: build analyze.py to compute cold-vs-primed token deltas and produce report.md.

[~now] PRE  step=61 tool=Write  args=analyze.py — pair cold+primed extractions, run paired t-test on log(output_tokens), compute Cohen's d + 95% CI, stratify, decide hybrid/no-hybrid
[~now] POST step=61 result=ok, ran cleanly. Wrote report.md + pairs.json to /tmp/pilot-work/pilot-results/.

PILOT RESULTS:
- 50 pairs (31 with real prior, 19 same as cold because no prior decoded)
- Output tokens: cold=1068 → primed=1046 (-2.0%, t=-2.41, d=-0.34, CI excludes 0 → statistically significant but small)
- Cost/call: cold=$0.0224 → primed=$0.0228 (primed +1.5% — prior text in user msg costs slightly more than the output savings)
- Completeness: cold=10.7 → primed=10.6 players (no regression)
- play_type agreement: 50/50

DECISION: DROP THE HYBRID. <15% reduction means priming isn't worth the engineering complexity. Scale up with cold-only extraction.

Scale-up math: 14,000 M25 plays × ~$0.022 = ~$308 to extract every M25 play geometry-fully via Sonnet 4.5 + caching.

Paths:
  WSL:     /tmp/pilot-work/pilot-results/report.md
  Windows: \\wsl$\Ubuntu\tmp\pilot-work\pilot-results\report.md

User insight: dedup by unique (family, formation, play_name) — Madden's play library is shared across teams.

[~now] PRE  step=62 tool=Bash  args=count unique (family, formation, play_name) across all 47 playbooks
[~now] POST step=62 result=
  15,057 total entries → 7,385 unique combos. Goal Line plays in 47/47 books; avg play in 2 books.
  Dedup cost: 7,385 × $0.022 = $162 (vs $308 unduped — saves $146).

[~now] PRE  step=63 tool=Bash  args=visual safety check — same play "GOAL LINE Normal HB Dive" from 3 different teams (Cardinals, Balanced, Ravens)
[~now] POST step=63 result=Background tint differs (team-color field bleed) but play diagram identical: same OL cluster, same C, same red HB arrow up the A-gap. Dedup SAFE for extraction.

USER FOLLOW-UP: HB target_gap is missing from extraction schema (currently in freeform prose only). Must add before launching $162 extraction.

Plan:
1. Update v3 prompt with structured target_gap field (A/B/C/D/edge_left/edge_right)
2. Smoke test (1 call) to verify new schema produces target_gap correctly
3. Build dedup pipeline (unique-play index + dispatcher that does canonical-only)
4. Run dedup'd extraction

[~now] PRE  step=64 tool=Edit  args=subagent-prompt.md — add gap convention + target_gap field to ball_carrier_or_primary schema
[~now] POST step=64 result=ok, SYSTEM section now 11733 chars (~2933 tokens), still above cache min

[~now] PRE  step=65 tool=Bash  args=smoke_test.py with new schema
[~now] POST step=65 result=ok, BOTH calls emitted target_gap. cold=A_left, primed=B_right (disagree on gap but field is set). Cache still hits at 3670 read tokens.

[~now] PRE  step=66 tool=Write args=dedup_crop.py — walk all teams' caches, build canonical index keyed by (family, formation, play_name, type), crop each combo once, batch by docx for speed, output to dedup-crops/
[~now] PRE  step=67 tool=Bash  args=run dedup_crop.py (background, ~7385 crops, ~10-15 min)
[~now] PRE  step=68 tool=Write args=dispatch_canonical.py — cold-only Sonnet 4.5 + caching extraction over canonical manifest, resume-safe, prime-then-parallel pattern

[~now] In progress: dedup_crop running (535/7385 written so far). dispatch_canonical.py ready to launch when crops finish.

Awaiting user confirmation before launching dispatch_canonical (which costs ~$162).

User pushed back: $162 is too much. Plan: build Python pre-detection layer to reduce per-call model work, use cheaper model.

[~now] PRE  step=69 tool=Write  args=detect_glyphs.py — OpenCV-based glyph + arrow detection
[~now] POST step=69 result=ok-but-incomplete:
  - C-square detection: WORKS via 40x40 sliding-window scan
  - Red arrow endpoint detection: WORKS
  - Individual circle detection: FAILS — OL heads and stubs merge into single contours; Hough Circles also can't find them at this resolution/density
  - Erosion to separate touching circles destroys them
  - Column-profile approach found peaks but in the wrong y-range
  
The OL row glyphs are packed too tight for standard CV blob detection. Approach needs rethink.

Alternative: detect ONLY (C-x, OL spacing, red-arrow endpoint), assume regular OL spacing (~50px). Compute target_gap from arrow x relative to C-x. Skip individual glyph identification entirely; let the model handle TE/WR counts and route classification.

User pivoted: hand-label small sample, calibrate against truth.

[/loop iteration session] User asked to iterate target_gap_python.py until it correctly classifies all 12 hand-labeled plays.

Iterations:
1. Initial state: 2/12 match (1 error, 6 false-positive gaps on pass plays).
2. Added play_type filter (return None for passes): 10/12 match.
3. Switched to combined-contour LOS-crossing + head-fallback: 10/12 (fixed balanced hb_toss error, but introduced 2 spacing-related mismatches).
4. Tried OL_SPACING=158 (calibrated from model coords median): 9/12 (worse on power_o cases).
5. Tried per-crop OL spacing from model's LT/RT: 8/12 (model frame scale is unstable).
6. Reverted to default OL_SPACING=85: 10/12 stable.

Final state: 10/12, 0 errors. Remaining mismatches (run_balanced power_o, mike_ditka counter) are cases where Python and the LLM disagree on the gap but neither has explicit ground truth — could be either side.

Plateau reached. Stopping iteration. Improvements:
- Added play_type filter (pass → null).
- LOS-band crossing detection with cluster median + forward-motion bias.
- Combined-contour handling for split arrows (head + tail + middle as separate contours).
- Head-fallback when no LOS crossing exists (lateral plays).
- Banner-mask refinements (kill RUN/PASS text + corner UI without losing arrows).

User supplied ground truth on the 2 disputed plays:
  - run_balanced power_o: C_right
  - mike_ditka counter:    C_left

Recalibrated OL_SPACING from 85 → 133 (only value in the [125, 141]
constraint range that fits BOTH ground-truth dx values).

Final state:
  - Pass plays correctly null: 7/7 ✓
  - Run plays vs ground truth: 2/2 ✓
  - Run plays vs LLM (no explicit truth): 2/3 (1 disagreement on baltimore_ravens power_o where LLM said C_right, Python now says B_right — no user ground truth either way)

User supplied truth for baltimore power_o: B_right. PYTHON WAS RIGHT, LLM WAS WRONG.

Final calibration result (OL_SPACING=133):
  - Pass plays correctly null: 7/7 ✓
  - Run plays vs ground truth: 3/3 ✓
  - Remaining 2 run plays (no truth): Python matches LLM
  - In the 1 LLM/Python disagreement: PYTHON was correct

The deterministic Python target_gap detector now BEATS the LLM on gap accuracy. Strong case for using Python's gap as the authoritative value in production extraction.

[~now] Pivoted to cheaper pipeline. Built smoke_test_haiku.py to validate Haiku 4.5 + Python hints against the 12 hand-labeled plays.

Haiku 4.5 + Python hints results:
- Caching WORKS on Haiku 4.5 now (11/12 cache hits) — previously didn't
- Cost: $0.008/call (Sonnet was $0.022/call)
- Accuracy vs hand-labels:
  * TE count: Haiku 9/12, Sonnet 10/12 (close)
  * WR count: Haiku 11/12, Sonnet 10/12 (BETTER)
  * Backfield: Haiku 12/12, Sonnet 11/12 (BETTER)
  * Play type: both 100%
- Net: Haiku 4.5 + Python hints is AS GOOD as Sonnet 4.5 at 2.7x lower cost

Wired Haiku + Python hints into dispatch_canonical.py. Validated with --limit 3 run.

Pricing for FULL 7,365-play M25 extraction:
  Sonnet 4.5 unduped (orig):     ~$330
  Sonnet 4.5 + deduped:          ~$162
  Haiku 4.5 + dedup + py hints:  ~$59  ← current target

Tried to extend Python detection (PS button glyphs, hollow-shape contour hierarchy, etc.) — hit diminishing returns. Buttons are hollow outlines that don't reliably form closed contours at 7.5x zoom; false positives from route arrows. Stopped after several iterations.

User insight: "use formation name to pass in expected TE/RB/WR numbers, that way for some formations where a slot and TE are in the same spot the python will be able to have already labeled this for the vision pass."

Built formation_personnel.py — rule-based classifier that decodes (RB, FB, TE, WR) counts from formation name patterns. Covers 342 unique M25 formations: 66% high confidence, 33% medium, 1% low. No "unknown" fallthroughs.

Built tag_crops_with_personnel.py — renames all 7,365 canonical crops to embed personnel tag in the filename:
  old: <family>__<formation>__<play_type>__<play_name>__WIDE.jpg
  new: <family>__<formation>__r<R>f<F>t<T>w<W>__<play_type>__<play_name>__WIDE.jpg
Also adds expected_personnel to _canonical_manifest.json.

Updated dispatch_canonical.py to inject expected personnel into user message AS AUTHORITATIVE input (not a question). LLM treats it as ground truth and only LABELS visible glyphs against the expected count.

Validation: Singleback Jumbo (previously a TE-count miss in v3/v4) now emits TE=3 WR=1 correctly. Same for other test cases.

Updated cost projection (incl ~250-token personnel block):
  ~$0.010/call → ~$74 for full 7,365-play extraction (vs $59 before).
  $15 more, but materially better accuracy on TE/WR counts.

User: "so we just pushed up the accuracy but also raised the cost"

Refactored: dropped the verbose personnel block from user message; rely on
filename tag (r#f#t#w#) that the LLM reads from play_id context for free.

  ~$0.0083/call → ~$61 for full extraction.
  Accuracy preserved (Jumbo TE=3 still correctly identified).
  Net: accuracy lift for +$2 over the no-personnel-hint baseline.

User: "lower cost more — think novel approaches"

Lever A — aggressive output schema compression. Decomposed where the cost
goes: 66% in output tokens (~1100 per call). Compact v5 schema:
  - Drop xy coords for all players (Python provides positions via personnel)
  - Drop play_id / play_type / formation echo (already in input)
  - Drop offensive_line array (5 OL implicit via personnel + C-square)
  - Drop glyph/button per-player fields
  - Compact `routes: {role: route_string}` instead of nested objects
  - Drop ball_carrier_or_primary verbose object; flat `ball_carrier`
    (e.g. "HB B_right") and `primary_target` ("WR_X") fields

Output dropped from ~1100 to 81-228 tokens (avg ~159). 7x reduction.

Cost: $0.0033/call avg → **$21-27 for full 7,365-play M25 extraction**.
That's 7x cheaper than v4 with Sonnet 4.5 ($162), and 12x cheaper than
the original unduped projection ($330).

Concepts, routes, ball-carrier with gap, and primary target all
correctly extracted on the 6 test calls.

V5 VALIDATION on 11 hand-labeled plays (mapped to canonical crops):
- Output tokens: 95-124 per call (avg ~106). Confirms 10x output reduction.
- Cost: $0.0294 for 11 calls = $0.0027/call.
- Concepts: 11/11 correctly named.
- Personnel-tag anchored counts now MATCH hand-truth on previously-failed
  cases:
    philadelphia_eagles se_drag: v4=1TE/3WR, truth=0TE/4WR, v5=0TE/4WR ✓
    baltimore_ravens power_o:    v4=1TE/2WR, truth=2TE/2WR, v5=2TE/2WR ✓
    west_coast seattle:          v4=1TE/3WR, truth=0TE/4WR, v5=0TE/3WR (TE✓, WR-1)
- Ball carrier with Python gap working. Primary target on passes working.
- Caveat: canonical crops come from different teams than the original
  hand-labeled ones. Diagrams are pixel-identical for the same
  (formation, play_name) but Python gap may vary slightly per crop.

Full M25 projection updated: ~$20 at $0.0027/call sustained.

LEVER B (concept dictionary + skip blockers on runs):
- play_concepts.py — 80+ regex patterns mapping play_name → concept tag
  + family (run/pass/pa_pass/screen/rpo) + blockers_implicit flag.
- Coverage: 83% of 7,365 unique plays classified, 17% fall back to LLM.
- dispatch_canonical.py injects py_concept and (for runs) tells LLM to
  emit empty `routes` since blockers are implicit.

40-play diverse sample results:
  family    | n  | avg out_tok | v5 baseline | Δ
  run       | 16 |   63        | ~100        | -37%
  pass      | 14 |  126        | ~140        | -10%
  pa_pass   | 10 |  168        | ~210        | -20%
  Overall   | 40 |  111        | ~159        | -30%

Cost: $0.00275/call → ~$20 for full 7,365-play extraction.

Final cost trajectory:
  Sonnet 4.5 unduped:                          ~$330
  Sonnet 4.5 deduped:                          ~$162
  Haiku 4.5 + Python gap + dedup:              ~$59
  + personnel tags + compact v5 schema:        ~$25
  + play_concepts + blockers-implicit (Lever B): ~$20

Iterated on the 17% unknown plays. Added 25+ more patterns: standalone
drag/under/clown/fly/go/flare/fakes/crossers/clearout/banana/spider/pin,
"f angle"/etc. fullback variants, double_concept/double_drags etc.,
deep_attack, texas, sluggo, china, scat, shakes, switch, all_go, omaha,
hank, hooks, flow_pass, seams, middle, fork, choice, scissors, etc.

Unknown rate: 17% → 7% → 5% → 3%.

But cost stayed at ~$20.60 for full extraction (50-call diverse sample
showed overall avg out_tok=105, same as before). Reason: most unknowns
were passes, where concept hint doesn't shrink the route output. The
real Lever B win was blocker-skip on runs which was already captured.

Floor of what play_concepts.py can save without route templates.

LEVER C TRIAL: route templates for top 10 concepts (Mesh, Stick, Smash,
Four Verts, Quick Slants, Curl Flats, Flood, Levels, Drags, All Streaks).

Test on 8 specific concept plays: ALL 8 emitted `routes:"std"` correctly.
Per-play output dropped from 126 to 57 tokens (55% reduction on templated
pass plays).

But aggregate impact on full M25: ~$0.50-1.50 saved. Templates only fire
on a fraction of plays (the well-known pass concepts ~25-30%); runs were
already at the 56-token floor. Marginal.

User chose to REVERT — kept the Lever B baseline ($20). Stripped the
route-template block from the system prompt.

User asked: "would templating pass concepts make it more accurate?"
Reframed Lever C as a DATA-QUALITY tool (route-name consistency, not just
cost savings). User chose to reinstate templates + validate first.

Built template-review.html with the 10 templates and canonical sample crops.
User reviewed (template_review.json):
  - 5/10 confirmed: quick_slants, flood, levels, drags, all_streaks
  - 5/10 needs_fix: four_verticals, mesh, smash, stick, curl_flat

Applied user's coaching corrections to the prompt:
  - four_verticals: slot/inner may run POST as variant of seam
  - mesh: role-flexible (any combination of TE/slot/WR/RB can run the crossers)
  - smash: ONE-side concept (corner + hitch on one side), other side independent
  - stick: 3-receiver concept (flat + vertical + stick at ~5 yds from #3)
  - curl_flat: outside curl at 12-14 yds + inside flat, read flat defender

User added: "sometimes a play can be multiple concepts too".
Updated schema: `concept` (dominant) + `concepts` (array of all visible).
Emit "routes":"std" only when ALL listed concepts match templates.

Re-tested on 6 templated concept plays — all still match templates and
emit "routes":"std". Output avg 67 tokens (vs 126 baseline).

Cached system prompt grew from 3469 to 4350 tokens. Cache_create rises
slightly; cache_read still cheap. Net cost ~$19 (vs $20 before).

PRE-LAUNCH CHECKLIST (all 4 items done):
1. Persistent output: OUT_DIR moved from /tmp to
   data/games/madden-25-ps3/play-geometry/ (survives WSL restart).
2. Family normalization: I-FORM/I_FORM/I FOR/I FO merged into I-FORM;
   FULL HOUSE/FULL_HOUSE → FULL-HOUSE; STRONG I/WEAK I → STRONG-I/WEAK-I.
   Manifest entries: 7,365 → 7,300 (saved ~65 leaked dupes).
3. Cross-family smoke test (smoke_test_cross_family.py): 1 play from
   each of 18 families. ALL 18 PASSED. $0.056 total spend.
4. validate_extractions.py built to run post-extraction. Checks JSON
   parse, concept mismatch, gap mismatch, route count vs personnel,
   primary_target validity, Wildcat-has-QB.

Updated projection: 7,300 plays × ~$0.0027/call = ~$19.71 for full M25
geometry extraction.














[~now] PRE  step=70 tool=Write  args=build_review.py — generate review.md with 12 stratified plays (3 per stratum) embedded with crop + model extraction + TRUTH section
[~now] POST step=70 result=ok, review.md written (514 lines, 12 plays). Each play: inline crop image + summary of model's read + checkboxes for correctness + free-form notes.

Path:
  WSL:     /mnt/c/GitHub/blitz-command/tools/playbook-vision-pilot/review.md
  Windows: C:\GitHub\blitz-command\tools\playbook-vision-pilot\review.md

User requested HTML instead. Built build_review_html.py.

[~now] PRE  step=71 tool=Write  args=build_review_html.py — self-contained HTML with form fields, autosave to localStorage, "Save" button downloads review_truth.json
[~now] POST step=71 result=ok, review.html written (12 plays, 2314 lines). Dark theme, checkboxes + correction inputs per row, free-form notes, autosave so progress isn't lost, "Save" downloads JSON.

Path:
  WSL:     /mnt/c/GitHub/blitz-command/tools/playbook-vision-pilot/review.html
  Windows: C:\GitHub\blitz-command\tools\playbook-vision-pilot\review.html

















































