"""Registry of analysis choices (the "garden of forking paths").

Every judgement call in the analysis lives here, never hard-coded in a step.
Each choice has a default, the alternatives we considered, a one-line reason
for the default, and the first step that reads it.

To run with another value:      python run_all.py --set price_resolution=hourly
To compare several values:      python run_all.py --sweep price_resolution=native,hourly
Non-default runs write to variants/<name>/ so the default results stay intact.

When you add a choice here, also add a line to notes/decisions.md.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Choice:
    name: str
    default: str
    alternatives: tuple  # other values we considered
    reason: str  # one line: why the default
    first_step: str  # first step that reads it, e.g. "01_fetch"
    open_ended: bool = False  # True: any value of the right form is allowed


CHOICES = {
    c.name: c
    for c in [
        Choice(
            name="bidding_zone",
            default="FI",
            alternatives=("SE1", "EE"),
            reason="The research question is about Finland; neighbours allow comparison.",
            first_step="01_fetch",
        ),
        Choice(
            name="sample_start",
            default="2022-01-01",
            alternatives=("2015-01-01", "2023-01-01", "2025-10-01"),
            reason="Includes the 2022 price crisis; 2025-10-01 starts the 15-minute era.",
            first_step="01_fetch",
            open_ended=True,
        ),
        Choice(
            name="sample_end",
            default="2026-10-31",
            alternatives=("2025-09-30", "2025-12-31"),
            reason="Last full month before the project started; fixed so reruns agree.",
            first_step="01_fetch",
            open_ended=True,
        ),
        Choice(
            name="price_resolution",
            default="native",
            alternatives=("hourly", "15min"),
            reason="Keep prices as traded: hourly until 2025-09-30, 15 minutes after.",
            first_step="02_process",
        ),
    ]
}


def check_value(name, value):
    """Return value if it is allowed for choice `name`, else raise ValueError."""
    if name not in CHOICES:
        known = ", ".join(sorted(CHOICES))
        raise ValueError(f"Unknown choice '{name}'. Known choices: {known}")
    choice = CHOICES[name]
    allowed = (choice.default,) + choice.alternatives
    if choice.open_ended or value in allowed:
        return value
    raise ValueError(
        f"Value '{value}' not allowed for '{name}'. Allowed: {', '.join(allowed)}"
    )


def resolve(overrides):
    """All choices with their values: defaults, replaced by any overrides."""
    settings = {name: c.default for name, c in CHOICES.items()}
    for name, value in overrides.items():
        settings[name] = check_value(name, value)
    return settings


def variant_name(settings):
    """Folder name for a run, or None when every choice is at its default.

    Only non-default choices appear, sorted by name, so the same settings
    always give the same folder: e.g. 'price_resolution-hourly__sample_start-2023-01-01'.
    """
    changed = [
        f"{name}-{value}"
        for name, value in sorted(settings.items())
        if value != CHOICES[name].default
    ]
    return "__".join(changed) if changed else None
