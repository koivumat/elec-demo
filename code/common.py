"""Helpers shared by every step script.

- ROOT and output_dir(): where files go (variants get their own folder)
- start_step(): read --set name=value from the command line
- read_secret() and mask(): load API keys from .env and hide them in text
- say(): print plain ASCII with secrets masked
- Report: build the human-readable check report checks/NN_name.md
"""

import argparse
import re
import sys
import traceback
from pathlib import Path

from dotenv import dotenv_values

import choices

ROOT = Path(__file__).resolve().parent.parent

# A zone keeps its colour in every figure (checked with a colour validator
# for colour-blind readers; see notes/decisions.md).
ZONE_COLORS = {"FI": "#257de0", "SE1": "#f47230", "EE": "#00b894",
               "SE3": "#f2a600", "DE": "#ee7fac"}

# ---------------------------------------------------------------- settings


def parse_set_args(pairs):
    """Turn ['a=1', 'b=2'] into {'a': '1', 'b': '2'}."""
    overrides = {}
    for pair in pairs or []:
        if "=" not in pair:
            raise ValueError(f"Expected name=value, got '{pair}'")
        name, value = pair.split("=", 1)
        overrides[name.strip()] = value.strip()
    return overrides


def start_step(description):
    """Read the command line of a step script.

    Returns (settings, variant): all choices with their values, and the
    variant folder name (None for the default run).
    """
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument(
        "--set", action="append", metavar="NAME=VALUE", help="change a choice"
    )
    args = parser.parse_args()
    try:
        settings = choices.resolve(parse_set_args(args.set))
    except ValueError as err:
        say(f"ERROR: {err}")
        sys.exit(2)
    return settings, choices.variant_name(settings)


def output_dir(kind, variant=None):
    """Folder for outputs of one kind ('checks', 'results', 'figures',
    'data/processed'). Non-default runs go under variants/<variant>/."""
    base = ROOT if variant is None else ROOT / "variants" / variant
    folder = base / kind
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def rel(path):
    """Path relative to the project root, with forward slashes (for reports)."""
    return Path(path).resolve().relative_to(ROOT).as_posix()


# ----------------------------------------------------------------- secrets

SECRET_NAMES = ("ENTSOE_API_KEY", "FINGRID_API_KEY")

# Patterns that carry a key in URLs or headers, whatever its value.
_KEY_PATTERNS = [
    re.compile(r"(securityToken=)[^&\s'\"]+", re.IGNORECASE),
    re.compile(r"(x-api-key['\"]?\s*[:=]\s*['\"]?)[^&\s'\",}]+", re.IGNORECASE),
]


def read_secret(name, env_file=None):
    """Value of `name` from .env, or None. Never printed by this code."""
    env_file = Path(env_file) if env_file else ROOT / ".env"
    if not env_file.exists():
        return None
    value = dotenv_values(env_file).get(name)
    if value is None or value.strip() == "" or value.strip() == "your-token-here":
        return None
    return value.strip()


def mask(text, secrets=None):
    """Hide API keys in text: known key values and key-like URL parameters."""
    text = str(text)
    if secrets is None:
        secrets = [read_secret(n) for n in SECRET_NAMES]
    for secret in secrets:
        if secret:
            text = text.replace(secret, "***")
    for pattern in _KEY_PATTERNS:
        text = pattern.sub(r"\1***", text)
    return text


def say(message=""):
    """Print a line to the console: secrets masked, plain ASCII only."""
    safe = mask(message).encode("ascii", errors="replace").decode("ascii")
    print(safe, flush=True)


def run(main):
    """Run a step's main(). If it crashes, print the error with keys masked
    (the ENTSO-E client puts the key in request URLs, and URLs end up in
    error messages)."""
    try:
        main()
    except SystemExit:
        raise
    except Exception:
        say(traceback.format_exc())
        say("Step failed (error text above has API keys masked).")
        sys.exit(1)


# ------------------------------------------------------------------ report


class Report:
    """A check report in Markdown. Deterministic: no times, no absolute paths.

    Usage:
        rep = Report("00_setup_check", "Setup check")
        rep.text("Some sentence.")
        rep.table(["check", "status"], [["Python", "OK"]])
        rep.write(variant)
    """

    def __init__(self, step, title):
        self.step = step
        self.lines = [
            f"# Check report {step}: {title}",
            "",
            f"Written by `code/{step}.py`. Rerun with "
            f"`python run_all.py --steps {step[:2]}`.",
            "",
        ]

    def heading(self, text):
        self.lines += [f"## {text}", ""]

    def text(self, text):
        self.lines += [text, ""]

    def bullets(self, items):
        self.lines += [f"- {item}" for item in items] + [""]

    def table(self, header, rows):
        def cell(value):
            return str(value).replace("|", "\\|")

        self.lines.append("| " + " | ".join(cell(h) for h in header) + " |")
        self.lines.append("|" + "---|" * len(header))
        for row in rows:
            self.lines.append("| " + " | ".join(cell(v) for v in row) + " |")
        self.lines.append("")

    def choices_in_effect(self, settings):
        """Standard section: every choice, its value here, and its default."""
        self.heading("Choices in effect")
        rows = []
        for name, c in choices.CHOICES.items():
            value = settings[name]
            mark = "" if value == c.default else " (changed)"
            rows.append([name, value + mark, c.default, c.first_step, c.reason])
        self.table(["choice", "value", "default", "first step", "reason"], rows)

    def render(self):
        text = "\n".join(self.lines).rstrip() + "\n"
        text = mask(text)
        if str(ROOT) in text:
            raise ValueError("Report contains an absolute path; use rel().")
        return text

    def write(self, variant=None):
        """Write checks/<step>.md (or the variant's copy). Returns the path."""
        path = output_dir("checks", variant) / f"{self.step}.md"
        # newline="\n": the same bytes on Windows and Linux
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(self.render())
        return path
