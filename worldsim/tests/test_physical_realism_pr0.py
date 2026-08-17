"""PR-0 harness unit tests (must pass; no production physics changes)."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from worldsim.validation.physical_realism.absolute_maps import write_absolute_scalar_png
from worldsim.validation.physical_realism.checksums import array_checksum, dict_checksum
from worldsim.validation.physical_realism.fixtures import (
    january_dry_start_ramp,
    land_max_hits_scale,
    northward_impulse_result,
    precip_vs_available_q_overshoot,
)
from worldsim.validation.physical_realism.metrics import (
    land_hypsometry_metrics,
    moisture_annual_metrics,
)
from worldsim.validation.physical_realism.seed_suites import (
    AUDIT_BASELINE_COMMIT,
    PROFILE_GRIDS,
    QUICK_SEEDS,
    REALISM_SCHEMA_VERSION,
)


def test_seed_suites_and_profiles_stable() -> None:
    assert QUICK_SEEDS == (1, 42, 100)
    assert REALISM_SCHEMA_VERSION == 1
    assert len(AUDIT_BASELINE_COMMIT) == 40
    assert set(PROFILE_GRIDS) == {"quick", "atlas", "full"}
    assert PROFILE_GRIDS["quick"]["terrain"] == (256, 128)


def test_array_checksum_stable() -> None:
    a = np.arange(12, dtype=np.float64).reshape(3, 4)
    assert array_checksum(a) == array_checksum(a.copy())
    assert array_checksum(a) != array_checksum(a + 1.0)


def test_dict_checksum_order_invariant() -> None:
    assert dict_checksum({"a": 1, "b": 2}) == dict_checksum({"b": 2, "a": 1})


def test_absolute_map_writes_legend(tmp_path: Path) -> None:
    field = np.linspace(-100.0, 900.0, 20 * 30, dtype=np.float64).reshape(20, 30)
    ocean = np.zeros((20, 30), dtype=bool)
    ocean[:, :3] = True
    meta = write_absolute_scalar_png(
        tmp_path / "elev.png",
        field,
        lo=-200.0,
        hi=1000.0,
        unit="m",
        ocean_mask=ocean,
    )
    assert (tmp_path / "elev.png").is_file()
    assert (tmp_path / "elev.png.legend.json").is_file()
    assert meta["stretch"] == "absolute"
    assert meta["lo"] == -200.0


def test_hypsometry_metrics_synthetic() -> None:
    elev = np.array([[-100.0, 10.0, 2000.0], [-50.0, 500.0, 8000.0]])
    ocean = elev < 0
    m = land_hypsometry_metrics(elev, ocean)
    assert m["land_cells"] == 4
    assert m["max_m"] == 8000.0
    assert m["frac_above_5km"] == 0.25


def test_fixture_probes_run() -> None:
    """Harness probes after PR-4+ corrections (direction, budget, spin-up)."""
    impulse = northward_impulse_result()
    assert impulse["total_mass"] == pytest.approx(1.0, rel=0, abs=1e-6)
    # Annex §10.2: wind_v>0 moves moisture toward smaller j (north).
    assert impulse["mass_north_of_seed"] > impulse["mass_south_of_seed"]

    overshoot = precip_vs_available_q_overshoot()
    assert overshoot["max_overshoot"] <= 1e-9

    ramp = january_dry_start_ramp()
    monthly = ramp["monthly_land_mean_precip"]
    assert len(monthly) == 12
    assert ramp["max_minus_min"] / max(float(np.mean(monthly)), 1e-12) < 0.08

    hit = land_max_hits_scale(9000.0)
    # CR-5: production ``power_tail`` does not pin every peak to land_scale_m.
    assert hit["max_a"] != pytest.approx(hit["max_b"])
    assert hit["max_a"] < 9000.0
    assert hit["max_b"] < 9000.0


def test_moisture_metrics_shapes() -> None:
    precip = np.ones((8, 10), dtype=np.float64)
    ocean = np.zeros((8, 10), dtype=bool)
    ocean[:, :2] = True
    m = moisture_annual_metrics(precip, ocean)
    assert "land_mean" in m
    assert m["interior_coast_ratio"] == pytest.approx(1.0)
