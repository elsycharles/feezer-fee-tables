"""MVola (Yas, ex-Telma): HTML tables on https://www.mvola.mg/tarifs/."""

from __future__ import annotations

import re

from bs4 import BeautifulSoup

from .model import Grid, Interval, ScrapeError, normalize, parse_amount

NAME = "MVola"
URL = "https://www.mvola.mg/tarifs/"
DESCRIPTION = "Mobile money de Yas (ex-Telma)."
ICON = "phone_android"

_RANGE = re.compile(r"entre\s+([\d .]+?)\s+et\s+([\d .]+?)\s*ar", re.I)
_DATE = re.compile(r"\bau\s+(\d{2})[-/.](\d{2})[-/.](\d{4})\b", re.I)
_MIN_OTHER = re.compile(r"transfert\s+a\s+partir\s+de\s+([\d .]+?)\s*ar", re.I)

# (operation, keywords that identify the column header)
_WITHDRAWAL_COLUMNS = (("withdrawal", ("cash point",)),)
_TRANSFER_COLUMNS = (
    ("transfer_same", ("vers un abonne mvola",)),
    ("transfer_other", ("autres operateurs",)),
    ("transfer_unregistered", ("vers un non abonne",)),
)


def _rows(table) -> list[list[str]]:
    return [
        [cell.get_text(" ", strip=True) for cell in tr.find_all(["td", "th"])]
        for tr in table.find_all("tr")
    ]


def _column(header: list[str], keywords: tuple[str, ...]) -> int | None:
    for index, cell in enumerate(header):
        text = normalize(cell)
        if any(keyword in text for keyword in keywords):
            return index
    return None


def _intervals(rows: list[list[str]], column: int) -> list[Interval]:
    intervals = []
    for row in rows[1:]:
        if not row or column >= len(row):
            continue
        match = _RANGE.search(normalize(row[0]))
        if not match:
            continue  # e.g. "Retrait par un non abonné MVola"
        fee = parse_amount(row[column])
        if fee is None:
            continue  # "–": not available for this amount
        intervals.append(
            Interval(
                parse_amount(match.group(1)),
                parse_amount(match.group(2)),
                fee,
            )
        )
    return intervals


def parse(html: str) -> list[Grid]:
    soup = BeautifulSoup(html, "html.parser")
    text = normalize(soup.get_text(" "))
    date = _DATE.search(text)
    effective = f"{date.group(3)}-{date.group(2)}-{date.group(1)}" if date else None

    found: dict[str, list[Interval]] = {}
    for table in soup.find_all("table"):
        rows = _rows(table)
        if not rows or not rows[0]:
            continue
        title = normalize(rows[0][0])
        if title.startswith("retrait d'argent"):
            columns = _WITHDRAWAL_COLUMNS
        elif title.startswith("transfert d'argent"):
            columns = _TRANSFER_COLUMNS
        else:
            continue
        for operation, keywords in columns:
            column = _column(rows[0], keywords)
            if column is None or operation in found:
                continue
            intervals = _intervals(rows, column)
            if intervals:
                found[operation] = intervals

    expected = [op for op, _ in _WITHDRAWAL_COLUMNS + _TRANSFER_COLUMNS]
    missing = [op for op in expected if op not in found]
    if missing:
        raise ScrapeError(f"MVola: tables not found for {missing}")

    # Footnote: transfers to other operators start at 300 Ar.
    minimum = _MIN_OTHER.search(text)
    if minimum:
        first = found["transfer_other"][0]
        low = parse_amount(minimum.group(1))
        if low is not None and first.min < low < first.max:
            found["transfer_other"][0] = Interval(low, first.max, first.fee)

    return [
        Grid(
            name=NAME,
            operation=operation,
            description=DESCRIPTION,
            icon=ICON,
            source_url=URL,
            source_type="official",
            effective_date=effective,
            intervals=found[operation],
        )
        for operation in expected
    ]


def collect(fetcher) -> list[Grid]:
    return parse(fetcher.get(URL).text)
