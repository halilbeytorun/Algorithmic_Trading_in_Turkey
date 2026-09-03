# Algorithmic Trading in Turkey

## Overview

This project downloads daily data for a static list of BIST stocks and reports
whether the latest completed session has a 15-period RSI below 40.

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

## Tests

The tests use generated data and do not contact Yahoo Finance:

```bash
python3 -m unittest discover -s tests -v
```

## Limitations

- The static universe currently contains 29 symbols and is not an authoritative
  point-in-time BIST 30 constituent list.
- The current day is always excluded, even after the market closes.
- Yahoo Finance is an unofficial data source and downloads can fail or change.
- RSI is an indicator, not a prediction or investment recommendation.
