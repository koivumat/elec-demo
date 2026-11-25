"""Rerun the whole analysis, or parts of it.

    python run_all.py                       all steps that do not need the API
    python run_all.py --fetch               also the steps that download data
    python run_all.py --steps 00            only step 00 (also: 00,02 or 01-03)
    python run_all.py --set price_resolution=hourly
                                            change one choice (output goes to variants/)
    python run_all.py --sweep price_resolution=native,hourly
                                            run once per value (several --sweep: every combination)
    python run_all.py --latex               also compile paper/ and slides/ with pdflatex
    python run_all.py --list                show steps and choices, run nothing

Every pull request that adds or changes a step updates STEPS below.
"""

import argparse
import itertools
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "code"))

import choices  # noqa: E402  (needs the path above)
from common import parse_set_args, say  # noqa: E402


@dataclass(frozen=True)
class Step:
    number: str
    name: str
    needs_api: bool = False  # True: only runs with --fetch
    uses_choices: bool = True  # False: runs once, never per variant

    @property
    def script(self):
        return ROOT / "code" / f"{self.number}_{self.name}.py"


STEPS = [
    Step("00", "setup_check"),
    Step("01", "fetch", needs_api=True, uses_choices=False),
]

LATEX_FILES = [("paper", "paper.tex"), ("slides", "slides.tex")]


def select_steps(spec):
    """'00,02' or '01-03' or None (all) -> list of Steps."""
    if not spec:
        return list(STEPS)
    wanted = set()
    for part in spec.split(","):
        part = part.strip()
        if "-" in part:
            first, last = part.split("-")
            wanted.update(f"{n:02d}" for n in range(int(first), int(last) + 1))
        else:
            wanted.add(f"{int(part):02d}")
    unknown = wanted - {s.number for s in STEPS}
    if unknown:
        raise ValueError(f"Unknown step(s): {', '.join(sorted(unknown))}")
    return [s for s in STEPS if s.number in wanted]


def parse_sweeps(pairs):
    """['a=1,2', 'b=x,y'] -> list of override dicts, one per combination."""
    names, value_lists = [], []
    for pair in pairs or []:
        name, values = parse_set_args([pair]).popitem()
        names.append(name)
        value_lists.append([v.strip() for v in values.split(",")])
    return [dict(zip(names, combo)) for combo in itertools.product(*value_lists)]


def run_step(step, overrides):
    """Run one step script; stream its output with keys masked."""
    cmd = [sys.executable, str(step.script)]
    for name, value in overrides.items():
        cmd += ["--set", f"{name}={value}"]
    proc = subprocess.Popen(
        cmd, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, encoding="utf-8", errors="replace",
    )
    for line in proc.stdout:
        say("    " + line.rstrip())
    return proc.wait()


def compile_latex():
    if shutil.which("pdflatex") is None:
        say("ERROR: pdflatex not found. Install MiKTeX or TeX Live, or skip --latex.")
        return False
    for folder, tex in LATEX_FILES:
        say(f"LaTeX: {folder}/{tex}")
        for _ in range(2):  # twice, so references and page numbers settle
            result = subprocess.run(
                ["pdflatex", "-interaction=nonstopmode", "-halt-on-error", tex],
                cwd=ROOT / folder, capture_output=True, text=True,
                encoding="utf-8", errors="replace",
            )
            if result.returncode != 0:
                say(f"ERROR compiling {folder}/{tex}. Last lines of the log:")
                for line in result.stdout.splitlines()[-15:]:
                    say("    " + line)
                return False
        say(f"    wrote {folder}/{tex[:-4]}.pdf")
    return True


def show_list():
    say("Steps:")
    for s in STEPS:
        note = "  (needs API key: runs only with --fetch)" if s.needs_api else ""
        if not s.uses_choices:
            note += "  (reads no choices)"
        say(f"  {s.number}  {s.name}{note}")
    say("")
    say("Choices (name = default; alternatives; first step):")
    for c in choices.CHOICES.values():
        alts = ", ".join(c.alternatives) + (", ..." if c.open_ended else "")
        say(f"  {c.name} = {c.default}; {alts}; {c.first_step}")
        say(f"      {c.reason}")


def main():
    parser = argparse.ArgumentParser(
        description="Rerun the analysis.",
        formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__,
    )
    parser.add_argument("--fetch", action="store_true",
                        help="include steps that download data (need the API key)")
    parser.add_argument("--steps", help="which steps, e.g. 00 or 00,02 or 01-03")
    parser.add_argument("--set", action="append", metavar="NAME=VALUE",
                        help="change a choice (repeatable)")
    parser.add_argument("--sweep", action="append", metavar="NAME=A,B",
                        help="run once per value (repeatable: all combinations)")
    parser.add_argument("--latex", action="store_true",
                        help="compile paper and slides with pdflatex")
    parser.add_argument("--list", action="store_true",
                        help="show steps and choices, run nothing")
    args = parser.parse_args()

    if args.list:
        show_list()
        return 0

    try:
        steps = select_steps(args.steps)
        base = parse_set_args(args.set)
        runs = [{**base, **sweep} for sweep in parse_sweeps(args.sweep)]
        for overrides in runs:  # check every value before running anything
            choices.resolve(overrides)
    except ValueError as err:
        say(f"ERROR: {err}")
        return 2

    for run_number, overrides in enumerate(runs):
        variant = choices.variant_name(choices.resolve(overrides))
        say(f"=== Run: {'default' if variant is None else 'variants/' + variant}")
        for step in steps:
            if step.needs_api and not args.fetch:
                say(f"--- {step.number} {step.name}: skipped (needs API; add --fetch)")
                continue
            if not step.uses_choices and run_number > 0:
                say(f"--- {step.number} {step.name}: skipped (reads no choices; ran once)")
                continue
            say(f"--- {step.number} {step.name}")
            step_overrides = overrides if step.uses_choices else {}
            if run_step(step, step_overrides) != 0:
                say(f"STOPPED: step {step.number} failed.")
                return 1

    if args.latex and not compile_latex():
        return 1
    say("Done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
