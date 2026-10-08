# Algorithmic Trading in Turkey

## Overview

This project downloads daily data for the effective-dated BIST 30 universe and
reports whether the latest completed session has a 15-period RSI below 40.

The screener uses explicitly adjusted Yahoo Finance closing prices. It excludes
the current Istanbul calendar day's candle because that daily candle may still
be in progress. It is a market-data screener, not a live trading system, and it
does not place orders.

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

Each successful line contains the symbol, completed session date, adjusted
close, RSI value, and either `OK` or `WARNING`.

Validate all configured Yahoo Finance mappings without calculating RSI:

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

## Tests

The tests use generated data and do not contact Yahoo Finance:

```bash
python3 -m unittest discover -s tests -v
```

## Limitations

- The included universe is valid only for its documented effective period and
  must be updated after 2026-12-31.
- The current day is always excluded, even after the market closes.
- Yahoo Finance is an unofficial data source and downloads can fail or change.
- RSI is an indicator, not a prediction or investment recommendation.
