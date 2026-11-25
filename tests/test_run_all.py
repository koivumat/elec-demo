"""The master script picks the right steps and runs, and reports are clean."""

import subprocess
import sys
from pathlib import Path

import pytest

import common
import run_all

ROOT = Path(__file__).resolve().parent.parent


def test_select_steps_by_list_and_range():
    assert [s.number for s in run_all.select_steps(None)] == [s.number for s in run_all.STEPS]
    assert [s.number for s in run_all.select_steps("00")] == ["00"]
    assert [s.number for s in run_all.select_steps("0-0")] == ["00"]


def test_unknown_step_is_rejected():
    with pytest.raises(ValueError):
        run_all.select_steps("99")


def test_every_step_has_a_script():
    for step in run_all.STEPS:
        assert step.script.exists(), f"missing {step.script.name}"


def test_fetch_needs_the_api_and_runs_once():
    fetch = {s.number: s for s in run_all.STEPS}["01"]
    assert fetch.needs_api and not fetch.uses_choices


def test_plain_run_skips_the_download():
    out = subprocess.run(
        [sys.executable, "run_all.py", "--steps", "01"], cwd=ROOT,
        capture_output=True, check=True, text=True,
    ).stdout
    assert "01 fetch: skipped (needs API; add --fetch)" in out


def test_sweep_gives_every_combination():
    runs = run_all.parse_sweeps(["a=1,2", "b=x,y,z"])
    assert len(runs) == 6
    assert {"a": "2", "b": "z"} in runs


def test_no_sweep_gives_one_run():
    assert run_all.parse_sweeps(None) == [{}]


def test_list_runs_and_prints_ascii():
    out = subprocess.run(
        [sys.executable, "run_all.py", "--list"], cwd=ROOT,
        capture_output=True, check=True,
    ).stdout
    out.decode("ascii")  # fails if anything is not plain ASCII
    assert b"00  setup_check" in out


def test_report_is_deterministic_and_has_no_absolute_paths():
    def build():
        rep = common.Report("99_example", "Example")
        rep.table(["a", "b"], [[1, 2]])
        return rep.render()

    assert build() == build()
    assert str(ROOT) not in build()
