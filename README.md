# Text Boxing Career Game

A modular boxing career simulation with CLI and desktop GUI interfaces.

## Quick Start

### CLI

```bash
python3 -m boxing_game
```

### GUI (PySide6)

Install the GUI dependency locally:

```bash
python3 -m pip install --target ./.vendor PySide6
```

Launch the desktop app:

```bash
python3 -m boxing_game.gui
```

## Features

- Create a boxer at age 15 with height (ft/in), weight (lbs), and stance
- Auto-generated stats and deterministic aging profile based on body metrics
- Amateur progression through novice, regional, and national tiers
- Turn pro after meeting configurable readiness milestones (age, fights, points)
- Pro fight scheduling with purse offers, deductions, balance, and earnings
- Organisation-focused ranking progression (WBC / WBA / IBF / WBO)
- Multi-body sanctioning: a single bout can move rankings across multiple organisations
- Tunable sanctioning-policy probabilities via `rules/pro_career.json`
- Division changes (adjacent classes) with seeded ranking carryover from P4P strength
- Lineal championship tracking with vacancy logic (`#1 vs #2` and `#1 vs #3` fallback)
- Organisation title state by body/division with defense tracking
- Dedicated GUI rankings page with top-20 sanctioning-body + top-20 pound-for-pound views
- Clickable ranking rows with boxer detail panel (record, rating, division, lineal status)
- Round-based fight simulation with judges, decision methods (UD/SD/MD/DRAW), and stoppages
- Separate amateur and pro fight models with configurable style weights
- Post-fight wear driven by outcome, method, and rounds completed
- Fight-based experience system with level titles and in-fight composure bonus
- Inline GUI stat-training buttons beside the stats panel
- Pro money management: special camps, medical recovery, and hireable/upgradeable staff
- Training and fatigue loop with staff-passive modifiers
- Month-based aging with birthday progression and per-boxer aging profiles
- Dynamic aging profiles (peak age, decline onset/severity, IQ growth factor)
- Sports Science staff upgrades that reduce age decline and improve ring-IQ growth
- In-game retirement system with hard age cap and performance-based retirement chance
- Monthly AI world simulation for title movement and ranking drift
- Legacy save migration that backfills age progression from career calendar
- Save/load/delete career state as JSON with atomic writes
- Dedicated GUI save-management page (load/delete/rename/duplicate + metadata)
- Dedicated GUI World News panel (separate from event log)

## Architecture

### Package layout

```
boxing_game/
├── __init__.py            # Package root, re-exports run()
├── __main__.py            # CLI entry point
├── constants.py           # Shared constants (ages, org names, stat caps)
├── utils.py               # Shared utility helpers (clamping, coercion)
├── models.py              # Core dataclasses (Boxer, CareerState, etc.)
├── rules_registry.py      # JSON rule-file loader with LRU cache
├── game.py                # CLI orchestration
├── gui.py                 # Desktop GUI orchestration (PySide6)
└── modules/
    ├── aging_engine.py        # Deterministic aging-profile generation
    ├── amateur_circuit.py     # Opponent generation and amateur progression
    ├── attribute_engine.py    # Stat generation and training gains
    ├── career_clock.py        # Calendar and age progression
    ├── experience_engine.py   # XP gain, levels, and fight bonus
    ├── fight_aftermath.py     # Result-based post-fight fatigue/injury
    ├── fight_sim_engine.py    # Round-based fight simulation
    ├── player_profile.py      # Boxer creation and input validation
    ├── pro_career.py          # Pro transition, rankings, titles, P4P, finances
    ├── pro_spending.py        # Money-based pro actions and staff passives
    ├── rating_engine.py       # Weighted overall boxer rating
    ├── retirement_engine.py   # Retirement probability and career-end decisions
    ├── savegame.py            # Persistence (save/load/slot management)
    ├── weight_class_engine.py # Weight class assignment
    └── world_sim.py           # Monthly non-player world events
```

### Shared modules

- **`constants.py`** centralises magic numbers and string literals
  (`STARTING_AGE`, `ORGANIZATION_NAMES`, `MAX_FATIGUE`, `MAX_INJURY_RISK`,
  `MIN_STAT`, `MAX_STAT`, `CURRENT_SAVE_VERSION`) so every module uses a
  single source of truth.

- **`utils.py`** provides small utility functions (`clamp_int`,
  `clamp_float`, `clamp_stat`, `clamp_probability`, `coerce_int`) that
  were previously duplicated across six or more engine modules.

## Rules Configuration

Gameplay values are externalised in JSON files under `rules/`:

| File | Purpose |
|------|---------|
| `weight_classes.json` | Division weight limits and average heights |
| `attribute_model.json` | Base stats, training coefficients, and stat limits |
| `amateur_progression.json` | Tier brackets, point awards, and pro-gate requirements |
| `fight_model.json` | Fight simulation parameters (amateur and pro) |
| `experience_model.json` | XP gain, levels, and fight-bonus configuration |
| `pro_spending.json` | Camp costs, medical recovery, and staff upgrade trees |
| `pro_career.json` | Pro tiers, purse economy, organisations, sanctioning policy, and world sim |
| `aging_model.json` | Age brackets, stat deltas, and decline acceleration |
| `retirement_model.json` | Age bands, performance modifiers, and chance bounds |

You can rebalance gameplay by editing these files without changing module code.

## Turn Pro Condition

Current readiness gate (from `rules/amateur_progression.json`):

- `min_age`: `18`
- `min_fights`: `10`
- `min_points`: `100`
- Boxer must not already be pro

## Career Pacing Sim (Realism Check)

Run the built-in simulator to estimate fight counts and pro bouts/year under
fatigue + injury + training policies and compare against real-life active-pro ranges:

```bash
python3 tools/sim_career_pacing.py --runs 300 --retire-age 35
```

## Tests

Test files are provided under `tests/`. Run with:

```bash
python3 -m pytest -q
```

## Quality Improvements

- Pro ranking limits now use each organisation's configured `ranking_slots`
- Purse offers include `total_expenses` and shared formatted breakdown
- Save files include version checks with compatibility guardrails
- Save writes are atomic; load errors are normalised with clear messages
- Save metadata listing and slot operations (rename/duplicate/delete) through a dedicated GUI page
- Money sinks with gameplay impact: paid special camps, paid medical recovery, and hireable staff
- Boxer creation validates non-empty names
- CLI/GUI surface detailed pro-readiness progress (age, fights, points)
- Fight simulation validates round count input (`rounds >= 1`)
- Boxer profile shows an overall rating derived from weighted fight attributes
- Deterministic rankings snapshot generation used by the GUI rankings page
- Lineal championship state management and fight-result title transitions
- Pound-for-pound rankings and P4P-based seeded division entry
- Pro division-change flow with down-move penalty model and immediate lineal vacate
- Retirement logic with configurable age cap and performance-sensitive retirement chance
- Deterministic dynamic aging profiles and sports-science money upgrades for aging outcomes
- Result-sensitive post-fight wear (losses/stoppages and harder fights increase fatigue/injury)
- Multi-body sanctioning: one pro bout moves rankings in multiple organisations
- Monthly AI world simulation for sanctioning-body title changes and ambient ranking movement
- Rule-driven sanctioning probability tuning and a dedicated GUI World News panel
- Ranking snapshots enforce organisation champion alignment at `#1` with auto-repair
- Champion draws in organisation title fights keep the champion at `#1`
- Pro fight history stores structured sanctioning metadata per fight
- World simulation tuning is fully rule-driven via `rules/pro_career.json`
- Experience progression system tied to fight count/results, integrated into rating/fight sim
- Legacy saves backfill missing `experience_points` from total recorded fights
- Expanded automated test suite (64 tests) covering pro flow, save compatibility, validation,
  aging, experience, retirement, fight aftermath, world sim, and readiness reporting

Detailed audit and implementation notes are in `CHANGES_2026-02-06.md`.
