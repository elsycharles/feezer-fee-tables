"""Orange Money: PDF linked from https://www.orange.mg/fr/tarifs-orange-money.html."""

from __future__ import annotations

import io
import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .model import Grid, Interval, ScrapeError, normalize, parse_amount

NAME = "Orange Money"
PAGE_URL = "https://www.orange.mg/fr/tarifs-orange-money.html"
DESCRIPTION = "Mobile money d'Orange Madagascar."
ICON = "phone_android"

# (operation, keyword found in the header cell of its column)
_COLUMNS = (
    ("withdrawal", "fisintonam"),
    ("transfer_same", "#144#"),
    ("transfer_same_app", "appli"),
    ("transfer_other", "tambazotra"),
    ("transfer_microfinance", "microfinance"),
    ("transfer_unregistered", "rehetra"),
)

_MONTHS = {
    # Malagasy
    "janoary": 1, "febroary": 2, "martsa": 3, "aprily": 4, "mey": 5, "jona": 6,
    "jolay": 7, "aogositra": 8, "septambra": 9, "oktobra": 10, "novambra": 11,
    "desambra": 12,
    # French
    "janvier": 1, "fevrier": 2, "mars": 3, "avril": 4, "mai": 5, "juin": 6,
    "juillet": 7, "aout": 8, "septembre": 9, "octobre": 10, "novembre": 11,
    "decembre": 12,
}
_DATE = re.compile(r"(\d{1,2})\s+([a-z]+)\s+(\d{4})")
_AMOUNT_TOKEN = re.compile(r"^(?:\d[\d .]*|-|–)$")


def find_pdf_url(page_html: str, page_url: str = PAGE_URL) -> str:
    """Link to the fee PDF on the tariffs page."""
    soup = BeautifulSoup(page_html, "html.parser")
    links = [a["href"] for a in soup.find_all("a", href=True)]
    pdfs = [href for href in links if href.lower().split("?")[0].endswith(".pdf")]
    preferred = [href for href in pdfs if "tarif" in href.lower()]
    if not (preferred or pdfs):
        raise ScrapeError("Orange: no PDF link on the tariffs page")
    return urljoin(page_url, (preferred or pdfs)[0])


def _effective_date(text: str) -> str | None:
    for day, month, year in _DATE.findall(normalize(text)):
        if month in _MONTHS:
            return f"{year}-{_MONTHS[month]:02d}-{int(day):02d}"
    return None


def parse_tables(tables: list[list[list[str | None]]], text: str, pdf_url: str) -> list[Grid]:
    """Builds the grids from pdfplumber tables of the first page."""
    main = None
    for table in tables:
        header_text = normalize(" ".join(c or "" for row in table[:3] for c in row))
        if "fisintonam" in header_text and "minimum" in header_text:
            main = table
            break
    if main is None:
        raise ScrapeError("Orange: fee table not found in the PDF")

    columns: dict[str, int] = {}
    header_rows = 0
    for row_index, row in enumerate(main[:3]):
        for index, cell in enumerate(row):
            cell_text = normalize(cell)
            for operation, keyword in _COLUMNS:
                if keyword in cell_text and operation not in columns:
                    columns[operation] = index
            if cell_text == "minimum":
                header_rows = row_index + 1
    missing = [op for op, _ in _COLUMNS if op not in columns]
    if missing or header_rows == 0:
        raise ScrapeError(f"Orange: columns not found {missing}")

    def tokens(cell: str | None) -> list[str]:
        # Cells may hold several stacked rows ("5 000 001\n6 000 001") and
        # stray header text ("0%"): keep only amounts and dashes.
        return [
            t.strip()
            for t in (cell or "").split("\n")
            if _AMOUNT_TOKEN.match(t.strip())
        ]

    found: dict[str, list[Interval]] = {op: [] for op, _ in _COLUMNS}
    for row in main[header_rows:]:
        minimums = tokens(row[0] if row else None)
        maximums = tokens(row[1] if len(row) > 1 else None)
        if not minimums:
            continue
        if len(minimums) != len(maximums):
            raise ScrapeError(f"Orange: unaligned row {row}")
        for operation, index in columns.items():
            values = tokens(row[index] if index < len(row) else None)
            if len(values) != len(minimums):
                raise ScrapeError(f"Orange: unaligned column {operation} in {row}")
            for low, high, value in zip(minimums, maximums, values):
                fee = parse_amount(value)
                if fee is None:
                    continue
                found[operation].append(
                    Interval(parse_amount(low), parse_amount(high), fee)
                )

    effective = _effective_date(text)
    return [
        Grid(
            name=NAME,
            operation=operation,
            description=DESCRIPTION,
            icon=ICON,
            source_url=pdf_url,
            source_type="official",
            effective_date=effective,
            intervals=found[operation],
        )
        for operation, _ in _COLUMNS
    ]


def parse_pdf(data: bytes, pdf_url: str) -> list[Grid]:
    import pdfplumber  # heavy import, only needed here

    with pdfplumber.open(io.BytesIO(data)) as pdf:
        if not pdf.pages:
            raise ScrapeError("Orange: empty PDF")
        page = pdf.pages[0]
        return parse_tables(page.extract_tables(), page.extract_text() or "", pdf_url)


def collect(fetcher) -> list[Grid]:
    page = fetcher.get(PAGE_URL)
    pdf_url = find_pdf_url(page.text, page.url)
    return parse_pdf(fetcher.get(pdf_url).content, pdf_url)
