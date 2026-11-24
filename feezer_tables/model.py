"""Fee grid model, parsing helpers and validation."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

# Operation keys understood by the Feezer app.
OPERATIONS = (
    "withdrawal",  # cash-out at an agent / cash point
    "transfer_same",  # to a customer of the same operator
    "transfer_same_app",  # same, through the operator's app
    "transfer_other",  # to a customer of another operator
    "transfer_microfinance",  # to a microfinance institution
    "transfer_unregistered",  # to someone without an account
)


class ScrapeError(RuntimeError):
    """The source could not be read or did not contain the expected grids."""


class ValidationError(ValueError):
    """A grid is inconsistent and must not be published."""


@dataclass(frozen=True)
class Interval:
    min: float
    max: float
    fee: float
    type: str = "fixed"  # "fixed" or "percentage"

    def to_json(self) -> dict:
        def number(value: float):
            return int(value) if float(value).is_integer() else value

        return {
            "min": number(self.min),
            "max": number(self.max),
            "fee": number(self.fee),
            "type": self.type,
        }


@dataclass
class Grid:
    name: str
    operation: str
    description: str
    icon: str
    source_url: str
    source_type: str  # "official" (scraped) or "manual"
    effective_date: str | None  # ISO date published by the operator
    intervals: list[Interval] = field(default_factory=list)

    def key(self) -> tuple[str, str]:
        return (self.name.lower(), self.operation)

    def to_json(self) -> dict:
        return {
            "name": self.name,
            "operation": self.operation,
            "description": self.description,
            "icon": self.icon,
            "source": {
                "type": self.source_type,
                "url": self.source_url,
                "effectiveDate": self.effective_date,
            },
            "intervals": [i.to_json() for i in self.intervals],
        }

    @staticmethod
    def from_json(data: dict) -> "Grid":
        source = data.get("source") or {}
        return Grid(
            name=data["name"],
            operation=data["operation"],
            description=data.get("description", ""),
            icon=data.get("icon", "business"),
            source_url=source.get("url", ""),
            source_type=source.get("type", "manual"),
            effective_date=source.get("effectiveDate"),
            intervals=[
                Interval(
                    float(i["min"]),
                    float(i["max"]),
                    float(i["fee"]),
                    i.get("type", "fixed"),
                )
                for i in data["intervals"]
            ],
        )


def normalize(text: str | None) -> str:
    """Lower case, no accents, single spaces, unified apostrophes."""
    if not text:
        return ""
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = text.replace("’", "'").replace(" ", " ")
    return re.sub(r"\s+", " ", text).strip().lower()


_NUMBER = re.compile(r"^\d{1,3}(?:[ .  ]?\d{3})*$")


def parse_amount(text: str | None) -> float | None:
    """'1 001' -> 1001.0, 'GRATUIT' -> 0.0, '–' / '-' / '' -> None.

    Raises ValueError for anything else, so format changes are noticed.
    """
    value = normalize(text)
    value = re.sub(r"\(\d+\)|\*+", "", value).strip()  # footnote marks
    if value in ("", "-", "–", "—", "n/a"):
        return None
    if value in ("gratuit", "gratuite", "maimaim-poana", "free"):
        return 0.0
    compact = value.replace(" ", "")
    if _NUMBER.match(value) or compact.isdigit():
        return float(compact.replace(".", ""))
    raise ValueError(f"Unexpected amount: {text!r}")


def validate(grid: Grid) -> None:
    """Rejects incomplete or inconsistent grids."""
    where = f"{grid.name} / {grid.operation}"
    if grid.operation not in OPERATIONS:
        raise ValidationError(f"{where}: unknown operation")
    if len(grid.intervals) < 3:
        raise ValidationError(f"{where}: only {len(grid.intervals)} tiers")
    previous: Interval | None = None
    for interval in grid.intervals:
        if interval.type not in ("fixed", "percentage"):
            raise ValidationError(f"{where}: unknown fee type {interval.type}")
        if not 0 <= interval.min < interval.max <= 1e10:
            raise ValidationError(f"{where}: invalid range {interval}")
        if interval.fee < 0 or (interval.type == "percentage" and interval.fee > 100):
            raise ValidationError(f"{where}: invalid fee {interval}")
        if previous is not None and interval.min <= previous.max:
            raise ValidationError(f"{where}: overlapping or unsorted {interval}")
        previous = interval
