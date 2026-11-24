import json
from pathlib import Path

import pytest

from feezer_tables import build, manual, mvola, orange
from feezer_tables.model import (
    Grid,
    Interval,
    ScrapeError,
    ValidationError,
    parse_amount,
    validate,
)

FIXTURES = Path(__file__).parent / "fixtures"


def by_operation(grids):
    return {g.operation: g for g in grids}


# --- helpers --------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("1 001", 1001),
        ("98 000", 98000),
        ("100000001", 100000001),
        ("GRATUIT", 0),
        ("Gratuit (2)", 0),
        ("–", None),
        ("-", None),
        ("", None),
    ],
)
def test_parse_amount(text, expected):
    assert parse_amount(text) == expected


def test_parse_amount_rejects_unknown_formats():
    with pytest.raises(ValueError):
        parse_amount("1%")


def test_validate_rejects_overlaps():
    grid = Grid("X", "withdrawal", "", "", "", "official", None, [
        Interval(100, 1000, 10), Interval(1000, 2000, 20), Interval(2001, 3000, 30),
    ])
    with pytest.raises(ValidationError):
        validate(grid)


# --- MVola ----------------------------------------------------------------


def test_mvola_grids():
    grids = by_operation(mvola.parse((FIXTURES / "mvola_tarifs.html").read_text()))
    assert set(grids) == {
        "withdrawal", "transfer_same", "transfer_other", "transfer_unregistered",
    }
    for grid in grids.values():
        validate(grid)
        assert grid.name == "MVola"
        assert grid.effective_date == "2025-02-17"
        assert grid.source_url == "https://www.mvola.mg/tarifs/"

    withdrawal = grids["withdrawal"].intervals
    assert withdrawal[0] == Interval(100, 1000, 100)
    assert withdrawal[-1] == Interval(19000001, 20000000, 100000)
    assert len(withdrawal) == 29

    same = grids["transfer_same"].intervals
    assert same[0] == Interval(100, 1000, 70)
    assert Interval(500001, 1000000, 3200) in same
    assert same[-1] == Interval(19000001, 20000000, 31300)

    other = grids["transfer_other"].intervals
    assert other[0] == Interval(300, 1000, 200)  # footnote: from 300 Ar
    assert other[-1] == Interval(4000001, 5000000, 24000)  # "–" above 5 M

    assert grids["transfer_unregistered"].intervals[0] == Interval(100, 1000, 750)


def test_mvola_missing_table_is_an_error():
    with pytest.raises(ScrapeError):
        mvola.parse("<html><table><tr><td>RETRAIT D'ARGENT</td></tr></table></html>")


# --- Orange ---------------------------------------------------------------


def orange_grids():
    data = json.loads((FIXTURES / "orange_tables.json").read_text())
    return by_operation(orange.parse_tables(data["tables"], data["text"], "https://x/y.pdf"))


def test_orange_grids():
    grids = orange_grids()
    assert set(grids) == {
        "withdrawal", "transfer_same", "transfer_same_app", "transfer_other",
        "transfer_microfinance", "transfer_unregistered",
    }
    for grid in grids.values():
        validate(grid)
        assert grid.name == "Orange Money"
        assert grid.effective_date == "2025-02-01"

    assert grids["withdrawal"].intervals[0] == Interval(200, 1000, 100)
    assert grids["withdrawal"].intervals[-1] == Interval(9000001, 10000000, 53900)
    assert grids["transfer_same"].intervals[0] == Interval(200, 1000, 65)
    assert grids["transfer_same_app"].intervals[0] == Interval(200, 1000, 35)
    # Stacked rows in the PDF ("5 000 001\n6 000 001") are split correctly.
    assert Interval(6000001, 7000000, 5350) in grids["transfer_same_app"].intervals
    # Not available above 5 000 000.
    assert grids["transfer_other"].intervals[-1] == Interval(4000001, 5000000, 18600)
    assert grids["transfer_unregistered"].intervals[1] == Interval(1001, 5000, 225)


def test_orange_pdf_link():
    page = '<a href="/omg-b2c/resources/other/PLAN_TARIFS_ORANGE_MONEY.pdf">ici</a>'
    assert orange.find_pdf_url(page, "https://www.orange.mg/fr/tarifs-orange-money.html") == (
        "https://www.orange.mg/omg-b2c/resources/other/PLAN_TARIFS_ORANGE_MONEY.pdf"
    )
    with pytest.raises(ScrapeError):
        orange.find_pdf_url("<p>no link</p>")


# --- build ----------------------------------------------------------------


class FakeFetcher:
    pass


def test_build_keeps_previous_grids_when_a_source_fails(tmp_path, monkeypatch):
    mvola_grids = mvola.parse((FIXTURES / "mvola_tarifs.html").read_text())
    orange_previous = list(orange_grids().values())
    output = tmp_path / "fees.json"
    output.write_text(build.render(orange_previous, "2025-01-01"), encoding="utf-8")

    def failing(_):
        raise ScrapeError("site changed")

    monkeypatch.setattr(build, "SOURCES", (
        ("MVola", lambda _: mvola_grids, lambda g: g.name == "MVola"),
        ("Orange Money", failing, lambda g: g.name == "Orange Money"),
        ("manual sources", manual.collect, lambda g: g.source_type == "manual"),
    ))
    status = build.build(FakeFetcher(), output)
    assert status == 1  # reported as failed
    document = json.loads(output.read_text())
    names = {(p["name"], p["operation"]) for p in document["providers"]}
    assert ("Orange Money", "transfer_same_app") in names  # kept
    assert ("MVola", "transfer_same") in names
    assert ("Airtel Money", "withdrawal") in names
    assert document["updatedAt"] != "2025-01-01"  # content changed
    assert build.check(output) == 0


def test_build_does_not_touch_the_date_when_nothing_changes(tmp_path, monkeypatch):
    grids = list(orange_grids().values())
    output = tmp_path / "fees.json"
    output.write_text(build.render(grids, "2025-01-01"), encoding="utf-8")
    monkeypatch.setattr(build, "SOURCES", (
        ("Orange Money", lambda _: grids, lambda g: True),
    ))
    assert build.build(FakeFetcher(), output) == 0
    document = json.loads(output.read_text())
    assert document["updatedAt"] == "2025-01-01"
    assert document["checkedAt"] is not None


def test_published_file_is_valid():
    assert build.check() == 0
