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

- Create a 16-year-old boxer
- Input height in `ft/in` and weight in `lbs`
- Auto-generated stats based on height/weight and weight class
- Amateur progression tiers (novice, regional, national)
- Turn pro after readiness milestones
- Pro fight scheduling with purse offers, deductions, balance, and earnings
- Organization-focused ranking progression (WBC/WBA/IBF/WBO)
- Round-based amateur fight simulation with judges and stoppages
- Round-based pro fight simulation with separate pro model
- Training and fatigue loop
- Month-based aging with birthday progression and age effects
- Legacy save migration that backfills age progression from career calendar
- Save/load career state as JSON

## Module Boundaries

- `boxing_game/modules/player_profile.py`: boxer creation and input validation
- `boxing_game/modules/attribute_engine.py`: stat generation and training gains
- `boxing_game/modules/weight_class_engine.py`: weight class assignment
- `boxing_game/modules/fight_sim_engine.py`: fight simulation
- `boxing_game/modules/amateur_circuit.py`: opponent generation and progression
- `boxing_game/modules/pro_career.py`: pro transition, pro opponents, rankings, finances
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
- `rules/pro_career.json`
- `rules/aging_model.json`

You can rebalance gameplay by editing these files without changing module code.

## Turn Pro Condition

Current readiness gate (from `rules/amateur_progression.json`):

- `min_age`: `19`
- `min_fights`: `18`
- `min_points`: `170`
- Boxer must not already be pro

## Quality Improvements

- Pro ranking limits now use each organization's configured `ranking_slots` (no hardcoded rank ceiling).
- Purse offers now include `total_expenses` and shared formatted breakdown output.
- Save files now include version checks with compatibility guardrails.
- Boxer creation now validates non-empty names.
- Added `.gitignore` for Python/runtime artifacts.
- Expanded automated tests for pro flow, save compatibility, validation, and aging edge cases.

Detailed audit and implementation notes are in `CHANGES_2026-02-06.md`.

## Tests

Test files are provided under `tests/`.

```bash
PYTHONPATH=./.vendor python3 -m pytest -q
```
