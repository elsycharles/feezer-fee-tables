# Feezer fee tables

Mobile money fee grids for Madagascar, read every day from the operators'
official websites and published in [`fees.json`](fees.json) for the
[Feezer](https://github.com/elsycharles/feezer) app
(the "Update the fees" action).

```
https://raw.githubusercontent.com/elsycharles/feezer-fee-tables/main/fees.json
```

## Sources

| Operator | Source | Format | How |
|---|---|---|---|
| MVola (Yas, ex-Telma) | <https://www.mvola.mg/tarifs/> | HTML tables | scraped daily |
| Orange Money | PDF linked from <https://www.orange.mg/fr/tarifs-orange-money.html> | PDF | scraped daily |
| Airtel Money | [`sources/airtel.json`](sources/airtel.json) | — | **by hand**: airtel.mg refuses automated access (HTTP 403) |

Grids published for each operator:

| `operation` | Meaning | MVola | Orange | Airtel |
|---|---|---|---|---|
| `withdrawal` | cash-out at an agent / cash point | ✓ | ✓ | ✓ |
| `transfer_same` | to a customer of the same operator | ✓ | ✓ (#144#) | |
| `transfer_same_app` | same, through the operator's app | | ✓ | |
| `transfer_other` | to a customer of another operator | ✓ | ✓ | |
| `transfer_microfinance` | to a microfinance institution | | ✓ | |
| `transfer_unregistered` | to someone without an account (IzyCash for Orange) | ✓ | ✓ | |

## How it works

[`.github/workflows/update.yml`](.github/workflows/update.yml) runs every day
(and on demand from the *Actions* tab):

1. runs the unit tests on saved copies of the official tables (`tests/fixtures`);
2. scrapes the websites with an identified user agent
   (`FeezerFeeTablesBot`), respecting `robots.txt`;
3. validates every grid (sorted, no overlap, sensible amounts) and writes
   `fees.json`;
4. commits it. `checkedAt` changes every day; `updatedAt` only when a grid
   changes.

If a website changes and its scraper fails, **the previous grids of that
operator are kept** (the app never receives broken data) and the workflow is
marked as failed, so GitHub sends an email.

## Maintenance

```sh
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
python -m pytest -q                    # offline tests
python -m feezer_tables.build          # scrape and write fees.json
python -m feezer_tables.build --check  # validate fees.json
```

- **A scraper fails**: open the failed run, read the error, adapt
  `feezer_tables/mvola.py` or `feezer_tables/orange.py`, refresh the fixture in
  `tests/fixtures/` and update the tests.
- **Airtel changes its fees**: edit `sources/airtel.json` (and set
  `effectiveDate`). The current grid comes from the app's data and still has to
  be checked against Airtel's official grid.
- **A new operator**: add a module with a `collect(fetcher)` function returning
  `Grid`s, register it in `SOURCES` in `feezer_tables/build.py`, add a fixture
  and tests. If its website cannot be read automatically, add a file in
  `sources/` instead.

## Format (schema 2)

```json
{
  "schema": 2,
  "updatedAt": "2026-11-24",
  "checkedAt": "2026-11-24",
  "providers": [
    {
      "name": "MVola",
      "operation": "transfer_same",
      "description": "…",
      "icon": "phone_android",
      "source": {
        "type": "official",
        "url": "https://www.mvola.mg/tarifs/",
        "effectiveDate": "2025-02-17"
      },
      "intervals": [
        { "min": 100, "max": 1000, "fee": 70, "type": "fixed" }
      ]
    }
  ]
}
```

- `min` / `max`: amount sent in Ariary, both included; intervals never overlap.
- `fee`: Ariary (`fixed`) or percentage of the amount (`percentage`).
- `source.type`: `official` (scraped) or `manual`; `effectiveDate` is the date
  printed by the operator, when available.
- The app matches grids by `name` + `operation` and replaces only those.

Fees are the operators' public prices; always confirm with the operator before
an important transfer.
