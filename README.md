# Text Boxing Career Game

Phase 2 implementation of a modular boxing career game (CLI + GUI).

## Run (CLI)

```bash
python3 -m boxing_game
```

## Run (GUI)

Install GUI dependency locally:

```bash
python3 -m pip install --target ./.vendor PySide6
```

Launch desktop app:

```bash
python3 -m boxing_game.gui
```

## Current Features (Phase 2)

- Create a 15-year-old boxer
- Input height in `ft/in` and weight in `lbs`
- Auto-generated stats based on height/weight and weight class
- Amateur progression tiers (novice, regional, national)
- Turn pro after readiness milestones
- Pro fight scheduling with purse offers, deductions, balance, and earnings
- Organization-focused ranking progression (WBC/WBA/IBF/WBO)
- Multi-body sanctioning on one fight (cross-organization rank movement from a single bout)
- Tunable sanctioning policy probabilities via rules (cross-body frequency and overlap behavior)
- Division changes (adjacent classes) with seeded ranking carryover from P4P strength
- Lineal championship tracking with vacancy logic (`#1 vs #2` and `#1 vs #3` fallback)
- Dedicated GUI rankings page with top-20 sanctioning-body + top-20 pound-for-pound views
- Clickable ranking rows with boxer detail panel (record, rating, division, lineal status)
- Round-based amateur fight simulation with judges and stoppages
- Round-based pro fight simulation with separate pro model
- Fight outcomes now drive post-fight wear (fatigue/injury) by result, method, and rounds completed
- Fight-based experience system with level titles and in-fight composure bonus
- Inline GUI stat-training buttons beside the stats panel (no focus dropdown)
- Pro money management: special camps, medical recovery, and hire/upgradeable staff
- Training and fatigue loop
- Month-based aging with birthday progression and age effects
- Dynamic per-boxer aging profiles (peak age, decline onset/severity, IQ growth factor)
- Sports Science staff upgrades that reduce age decline and improve ring-IQ growth
- In-game retirement system with hard age cap + performance-based retirement chance
- Monthly AI world simulation for title movement and ranking drift context
- Legacy save migration that backfills age progression from career calendar
- Save/load/delete career state as JSON
- Dedicated GUI save-management page (load/delete/rename/duplicate + metadata)
- Dedicated GUI World News panel (separate from event log)

## Module Boundaries

- `boxing_game/modules/player_profile.py`: boxer creation and input validation
- `boxing_game/modules/attribute_engine.py`: stat generation and training gains
- `boxing_game/modules/weight_class_engine.py`: weight class assignment
- `boxing_game/modules/fight_sim_engine.py`: fight simulation
- `boxing_game/modules/fight_aftermath.py`: result-based post-fight fatigue/injury impact
- `boxing_game/modules/experience_engine.py`: experience gain, levels, and fight bonus
- `boxing_game/modules/aging_engine.py`: deterministic boxer aging-profile generation
- `boxing_game/modules/pro_spending.py`: money-based pro actions and staff passives
- `boxing_game/modules/retirement_engine.py`: retirement probability and career-end decisions
- `boxing_game/modules/amateur_circuit.py`: opponent generation and progression
- `boxing_game/modules/pro_career.py`: pro transition, opponents, rankings, lineal, P4P, division changes, finances
- `boxing_game/modules/world_sim.py`: monthly non-player world events (title changes and ranking drift)
- `boxing_game/modules/rating_engine.py`: weighted overall boxer rating
- `boxing_game/modules/career_clock.py`: calendar and age progression
- `boxing_game/modules/savegame.py`: persistence
- `boxing_game/rules_registry.py`: rule-file loading
- `boxing_game/game.py`: CLI orchestration
- `boxing_game/gui.py`: desktop GUI orchestration (PySide6)

## Rules Configuration

Gameplay values are externalized in:

- `rules/weight_classes.json`
- `rules/attribute_model.json`
- `rules/amateur_progression.json`
- `rules/fight_model.json`
- `rules/experience_model.json`
- `rules/pro_spending.json`
- `rules/pro_career.json`
- `rules/aging_model.json`
- `rules/retirement_model.json`

You can rebalance gameplay by editing these files without changing module code.

## Turn Pro Condition

Current readiness gate (from `rules/amateur_progression.json`):

- `min_age`: `18`
- `min_fights`: `10`
- `min_points`: `100`
- Boxer must not already be pro

## Quality Improvements

- Pro ranking limits now use each organization's configured `ranking_slots` (no hardcoded rank ceiling).
- Purse offers now include `total_expenses` and shared formatted breakdown output.
- Save files now include version checks with compatibility guardrails.
- Save writes are now atomic and load errors are normalized with clear save-specific messages.
- Added save metadata listing and slot operations (rename/duplicate/delete) through a dedicated GUI management page.
- Added money sinks with gameplay impact: paid special camps, paid medical recovery, and hireable staff passives.
- Boxer creation now validates non-empty names.
- CLI/GUI now surface detailed pro-readiness progress (age, fights, points).
- Fight simulation now validates round count input (`rounds >= 1`).
- Boxer profile now shows an overall rating derived from weighted fight attributes.
- Added deterministic rankings snapshot generation used by the GUI rankings page.
- Added lineal championship state management and fight-result title transitions.
- Added pound-for-pound rankings and P4P-based seeded division entry.
- Added pro division-change flow with down-move penalty model and immediate lineal vacate behavior.
- Added retirement logic with configurable age cap and performance-sensitive retirement chance.
- Added deterministic dynamic aging profiles and sports-science money upgrades that influence aging outcomes.
- Added result-sensitive post-fight wear so losses/stoppages and harder fights increase fatigue/injury more.
- Added multi-body sanctioning support so one pro bout can move rankings in multiple organizations.
- Added monthly AI world simulation for sanctioning-body title changes and ambient ranking movement.
- Added rule-driven sanctioning probability tuning and a dedicated GUI World News panel.
- Added an experience progression system tied to fight count/results and integrated into rating/fight sim.
- Legacy saves now backfill missing `experience_points` from total recorded fights.
- Added `.gitignore` for Python/runtime artifacts.
- Expanded automated tests for pro flow, save compatibility, validation, aging edge cases, and readiness reporting.

Detailed audit and implementation notes are in `CHANGES_2026-02-06.md`.

## Career Pacing Sim (Realism Check)

Run the built-in simulator to estimate fight counts and pro bouts/year under
fatigue + injury + training policies and compare against real-life active-pro ranges:

```bash
python3 tools/sim_career_pacing.py --runs 300 --retire-age 35
```

## Tests

Test files are provided under `tests/`.

```bash
PYTHONPATH=./.vendor python3 -m pytest -q
```
