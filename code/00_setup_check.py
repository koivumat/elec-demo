"""Step 00: check that this computer is ready for the project.

Checks the Python version, the installed packages against requirements.txt,
the project folders and the API key (only whether it is there, never its
value). Writes checks/00_setup_check.md.

Run:  python code/00_setup_check.py      (or: python run_all.py --steps 00)
"""

import sys
from importlib import metadata

from common import ROOT, Report, read_secret, run, say, start_step

STEP = "00_setup_check"
EXPECTED_PYTHON = "3.13"
FOLDERS = [
    "code", "tests", "data/raw", "data/processed", "checks", "results",
    "figures", "paper", "slides", "notes",
]


def read_requirements(path):
    """Pinned packages from requirements.txt as {name: version}."""
    pins = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.split("#")[0].strip()
        if "==" in line:
            name, version = line.split("==")
            pins[name.strip()] = version.strip()
    return pins


def installed_version(name):
    try:
        return metadata.version(name)
    except metadata.PackageNotFoundError:
        return "not installed"


def main():
    settings, variant = start_step(__doc__)
    rows = {}  # section -> list of [item, expected, seen, status]

    # Python
    seen = f"{sys.version_info.major}.{sys.version_info.minor}"
    status = "OK" if seen == EXPECTED_PYTHON else "PROBLEM"
    rows["Python"] = [["Python version", EXPECTED_PYTHON, seen, status]]

    # Packages
    pins = read_requirements(ROOT / "requirements.txt")
    rows["Packages (pinned in requirements.txt)"] = [
        [name, version, installed_version(name),
         "OK" if installed_version(name) == version else "PROBLEM"]
        for name, version in pins.items()
    ]

    # Folders
    rows["Project folders"] = [
        [folder + "/", "exists", "exists" if (ROOT / folder).is_dir() else "missing",
         "OK" if (ROOT / folder).is_dir() else "PROBLEM"]
        for folder in FOLDERS
    ]

    # Secrets: only presence, never the value
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
    example = (ROOT / ".env.example").read_text(encoding="utf-8")
    entsoe = read_secret("ENTSOE_API_KEY") is not None
    fingrid = read_secret("FINGRID_API_KEY") is not None
    rows["Secrets"] = [
        ["ENTSOE_API_KEY in .env", "found",
         "found (value not shown)" if entsoe else "NOT FOUND",
         "OK" if entsoe else "WARNING"],
        ["FINGRID_API_KEY in .env", "optional, not used yet",
         "found (value not shown)" if fingrid else "not set", "OK"],
        [".env listed in .gitignore", "yes",
         "yes" if ".env" in gitignore else "no",
         "OK" if ".env" in gitignore else "PROBLEM"],
        [".env.example holds a placeholder", "yes",
         "yes" if "ENTSOE_API_KEY=your-token-here" in example else "no",
         "OK" if "ENTSOE_API_KEY=your-token-here" in example else "PROBLEM"],
    ]

    # Count results
    statuses = [r[3] for section in rows.values() for r in section]
    counts = {s: statuses.count(s) for s in ("OK", "WARNING", "PROBLEM")}

    # Console
    for section, section_rows in rows.items():
        for item, expected, seen, status in section_rows:
            if status != "OK":
                say(f"[{status}] {section}: {item}: expected {expected}, seen {seen}")
    say(f"Setup check: {counts['OK']} OK, {counts['WARNING']} warning(s), "
        f"{counts['PROBLEM']} problem(s)")

    # Report
    rep = Report(STEP, "Setup check")
    rep.text(
        "Is this computer ready? Each row compares what we EXPECT with what "
        "we SEE on the machine that ran this script."
    )
    rep.heading("Summary")
    rep.table(["status", "count"], [[s, n] for s, n in counts.items()])
    for section, section_rows in rows.items():
        rep.heading(section)
        rep.table(["item", "expected", "seen", "status"], section_rows)
    rep.choices_in_effect(settings)
    rep.heading("What a person should check")
    rep.bullets([
        "Every row says OK. A PROBLEM must be fixed before the next step.",
        "ENTSOE_API_KEY says WARNING when .env is missing. Steps that "
        "download data (run with --fetch) need it; other steps do not.",
        "Python and package versions match on every computer: if your report "
        "differs from the committed one, your environment differs.",
        "The key value never appears here, only whether it was found.",
    ])
    path = rep.write(variant)
    say(f"Report written: {path.relative_to(ROOT).as_posix()}")

    sys.exit(1 if counts["PROBLEM"] else 0)


if __name__ == "__main__":
    run(main)
