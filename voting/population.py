"""
voting/population.py

Single source of truth for cohort/category population data and
race → eligible-population mapping for the Monsoon 2026 election.

Used by:
  - races_view   → voter_percentage  (votes / eligible_population × 100)
  - quorum_view  → quorum progress   (votes / quorum × 100, capped at 100%)
"""

# ── Batch populations ────────────────────────────────────────────────────────
BATCH_POPULATION = {
    "ug2023": {"population": 689,  "quorum": 276},
    "ug2024": {"population": 782,  "quorum": 313},
    "ug2025": {"population": 764,  "quorum": 306},
    "ug2026": {"population": 1048, "quorum": 419},
}

# ── Category populations ─────────────────────────────────────────────────────
CATEGORY_POPULATION = {
    "undergraduate":   {"population": 3283, "quorum": 1313},
    "yif":             {"population": 101,  "quorum": 40},
    "masters":         {"population": 144,  "quorum": 58},
    "phd":             {"population": 262,  "quorum": 105},
    "late_graduate":   {"population": 71,   "quorum": 28},
    "total":           {"population": 3861, "quorum": 1544},
}

# ── Race → population mapping ────────────────────────────────────────────────
# Each race_id maps to {eligible_population, quorum}.
# President/GenSec use the total student body.
# Council races use their specific batch or category.

RACE_POPULATION_MAP: dict[str, dict[str, int]] = {
    "president":             {"eligible_population": 3861, "quorum": 1544},
    "gensec":                {"eligible_population": 3861, "quorum": 1544},
    "council_1st_year":      {"eligible_population": 1048, "quorum": 419},
    "council_2nd_year":      {"eligible_population": 764,  "quorum": 306},
    "council_3rd_year":      {"eligible_population": 782,  "quorum": 313},
    "council_4th_year":      {"eligible_population": 689,  "quorum": 276},
    "council_yif":           {"eligible_population": 101,  "quorum": 40},
    "council_masters":       {"eligible_population": 144,  "quorum": 58},
    "council_phd":           {"eligible_population": 262,  "quorum": 105},
    "council_late_grad":     {"eligible_population": 71,   "quorum": 28},
    "council_undergraduate": {"eligible_population": 3283, "quorum": 1313},
}

# Fallback for unknown races
_FALLBACK = {"eligible_population": 0, "quorum": 0}


def get_race_population(race_id: str) -> dict[str, int]:
    """Return {eligible_population, quorum} for a given race_id."""
    return RACE_POPULATION_MAP.get(race_id, _FALLBACK)


def get_all_race_populations() -> dict[str, dict[str, int]]:
    """Return the full race → population map."""
    return RACE_POPULATION_MAP
