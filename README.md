# Algorithmic Trading in Turkey

## Overview

This project downloads daily data for the effective-dated BIST 30 universe and
investigates short-term momentum and long-term trends in both TRY and USD.

The screener requests two calendar years of explicitly adjusted Yahoo Finance
closing prices ending at the analysis cutoff, plus enough earlier USD/TRY data
for safe alignment. It excludes the cutoff date because that daily candle may
still be in progress. It is a market-data screener, not a live trading system,
and it does not place orders.

## Requirements

- Python 3.9 or newer
- pandas
- yfinance

Install the dependencies in a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

## Usage

```bash
python3 main.py
```

Each successful line contains the completed session date and the following
values in both TRY and USD:

- Adjusted close
- 15-period RSI
- 50-session and 200-session simple moving averages
- 12-month return based on 252 trading sessions
- Long-term trend direction and setup classification

Validate all configured stock and USD/TRY Yahoo Finance mappings without
calculating indicators:

```bash
python3 main.py --validate-universe
```

Use a specific effective date or an alternative universe file:

```bash
python3 main.py --as-of 2026-10-08 --universe config/bist30.csv
```

## BIST 30 Universe

`config/bist30.csv` contains quarterly snapshots with exactly 30 official
constituents, explicit Yahoo Finance mappings, effective dates, retrieval dates,
and source URLs. It currently covers Q3 and Q4 2026. The active Q4 snapshot
applies from 2026-10-01 through 2026-12-31; `TRMET` entered BIST 30 and `DSTKF`
left the index at the start of this period.

Sources:

- [Borsa Istanbul index weights](https://www.borsaistanbul.com/files/endeks_agirlik_ds_genel.csv),
  retrieved for the snapshots on 2026-09-03 and 2026-10-08
- [Official Q3 2026 index review](https://www.kap.org.tr/en/Bildirim/1619135), which announced no BIST 30 additions or removals
- [Official Q4 2026 index review](https://www.kap.org.tr/en/Bildirim/1666347), effective from 2026-10-01 through 2026-12-31

The loader rejects missing metadata, malformed dates or symbols, duplicate
mappings, expired snapshots, and any active universe that does not contain
exactly 30 constituents. Update the file when a new quarterly composition takes
effect. Yahoo Finance is used only as the price provider, not as the authority
for index membership.

## Currency And Trend Analysis

Yahoo Finance's `USDTRY=X` series is quoted as TRY per USD. Each historical
adjusted stock close is converted before calculating its USD indicators:

```text
adjusted_close_usd = adjusted_close_try / usdtry
```

Each Yahoo FX close is treated as available on the next calendar date. A stock
session therefore uses the latest previously completed FX close, never a later
or still-open daily FX observation. Earlier rates may be carried forward when
necessary, but rates more than seven calendar days old are rejected.

A long-term uptrend requires all three conditions in the relevant currency:

```text
close > SMA200
SMA50 > SMA200
SMA200 > its value 20 sessions earlier
```

Possible classifications are:

- `USD_RECOVERY_CANDIDATE`: USD RSI crossed strictly above 30 in a USD uptrend
- `USD_PULLBACK_WATCH`: USD RSI is below 40 in a USD uptrend
- `TRY_AND_USD_UPTREND`: both long-term trends are positive
- `TRY_ONLY_UPTREND`: the nominal TRY trend is not confirmed in USD
- `USD_ONLY_UPTREND`: only the USD-adjusted trend is positive
- `LOW_RSI_WITHOUT_UPTREND`: low RSI without a confirmed long-term uptrend
- `NO_CONFIRMED_UPTREND`: neither long-term uptrend is confirmed

CLI trend fields use `UP` or `NOT_UP`; `NOT_UP` can mean falling, sideways, or a
mixed trend and should not be interpreted as proof of a downtrend.

## Tests

The tests use generated data and do not contact Yahoo Finance:

```bash
python3 -m unittest discover -s tests -v
```

## Limitations

- The included universe is valid only for its documented effective period and
  must be updated after 2026-12-31.
- The current day is always excluded, even after the market closes.
- Future `--as-of` dates are rejected. Historical analysis requests its own
  two-year warm-up window and still requires a matching effective-dated universe.
- Yahoo Finance is an unofficial data source and downloads can fail or change.
- USD adjustment measures dollar-denominated performance, not Turkish
  inflation-adjusted purchasing power. CPI analysis would require a separate
  effective-dated inflation series.
- RSI is an indicator, not a prediction or investment recommendation.
