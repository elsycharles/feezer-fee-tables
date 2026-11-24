# Feezer fee tables

Reference mobile money fee grids downloaded by the Feezer app
("Update fees from the internet").

The app reads [`fees.json`](fees.json) from the `main` branch:

```
https://raw.githubusercontent.com/elsycharles/feezer-fee-tables/main/fees.json
```

## Updating the grids

1. Edit `fees.json` (on GitHub: open the file, click the pencil icon).
2. Change `updatedAt` to the date the new grid applies (`YYYY-MM-DD`).
3. Commit. Every app gets the new grid the next time the user taps
   "Update fees from the internet".

## Format

```json
{
  "updatedAt": "2025-10-14",
  "providers": [
    {
      "name": "YAS",
      "description": "…",
      "icon": "phone_android",
      "intervals": [
        { "min": 100, "max": 1000, "fee": 100, "type": "fixed" },
        { "min": 1001, "max": 5000, "fee": 1.5, "type": "percentage" }
      ]
    }
  ]
}
```

- `min` / `max`: amount sent, both included. Intervals of a provider must not overlap.
- `fee`: amount (`"fixed"`) or percentage of the amount sent (`"percentage"`, 0–100).
- Providers are matched by name (case-insensitive). The app replaces the grid of
  each listed provider and creates missing ones; other providers are untouched.
- An invalid file (overlap, max ≤ min…) is rejected by the app as a whole.
