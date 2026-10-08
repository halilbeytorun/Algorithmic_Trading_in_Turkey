"""Scan BIST 30 stocks for a low Relative Strength Index (RSI)."""

import argparse
import datetime
import sys
from pathlib import Path
from typing import Optional, Sequence

import pandas as pd

import helper


RSI_PERIOD = 15
RSI_LOWER_BAND = 40.0
RSI_COLUMN = "RSI"


def _rsi_value(average_gain: float, average_loss: float) -> float:
    if average_gain == 0 and average_loss == 0:
        return 50.0
    if average_loss == 0:
        return 100.0
    if average_gain == 0:
        return 0.0

    relative_strength = average_gain / average_loss
    return 100.0 - (100.0 / (1.0 + relative_strength))


def calculate_rsi(close: pd.Series, period: int = RSI_PERIOD) -> pd.Series:
    """Calculate RSI using Wilder's smoothing method."""
    if period <= 0:
        raise ValueError("RSI period must be greater than zero")

    prices = pd.to_numeric(close, errors="coerce").astype(float)
    if prices.isna().any():
        raise ValueError("Closing prices must contain only numeric values")
    if len(prices) < period + 1:
        raise ValueError(
            "At least {} closing prices are required for RSI({})".format(
                period + 1, period
            )
        )

    changes = prices.diff().iloc[1:]
    gains = changes.clip(lower=0.0)
    losses = -changes.clip(upper=0.0)

    average_gain = float(gains.iloc[:period].mean())
    average_loss = float(losses.iloc[:period].mean())
    rsi = pd.Series(index=prices.index, dtype="float64", name=RSI_COLUMN)
    rsi.iloc[period] = _rsi_value(average_gain, average_loss)

    for offset in range(period, len(changes)):
        average_gain = (
            average_gain * (period - 1) + float(gains.iloc[offset])
        ) / period
        average_loss = (
            average_loss * (period - 1) + float(losses.iloc[offset])
        ) / period
        rsi.iloc[offset + 1] = _rsi_value(average_gain, average_loss)

    return rsi


def latest_completed_row(
    data: pd.DataFrame, as_of_date: Optional[datetime.date] = None
) -> pd.Series:
    """Return the latest row before the current Istanbul calendar date.

    Excluding the current date prevents an in-progress daily candle from
    producing a signal. An exchange calendar can refine this policy later.
    """
    if data.empty:
        raise ValueError("Cannot select a completed row from empty data")

    if as_of_date is None:
        as_of_date = pd.Timestamp.now(tz="Europe/Istanbul").date()

    index = pd.DatetimeIndex(pd.to_datetime(data.index))
    if index.tz is not None:
        index = index.tz_convert("Europe/Istanbul")

    completed = data.loc[index.date < as_of_date]
    if RSI_COLUMN in completed.columns:
        completed = completed.dropna(subset=[RSI_COLUMN])
    if completed.empty:
        raise ValueError("No completed session with a calculated RSI is available")

    return completed.sort_index().iloc[-1]


def scan_stock(
    stock_name: str,
    yahoo_symbol: str,
    as_of_date: Optional[datetime.date] = None,
) -> pd.Series:
    data = helper.download_stock_data(
        stock_name, yahoo_symbol, minimum_rows=RSI_PERIOD + 1
    )
    analyzed = data.copy()
    analyzed[RSI_COLUMN] = calculate_rsi(analyzed["Close"], RSI_PERIOD)
    return latest_completed_row(analyzed, as_of_date)


def validate_provider_mappings(
    universe: Sequence[helper.UniverseEntry],
) -> int:
    """Check that every configured Yahoo symbol returns daily market data."""
    failures = 0

    for entry in universe:
        try:
            data = helper.download_stock_data(
                entry.symbol,
                entry.yahoo_symbol,
                period="5d",
                minimum_rows=1,
            )
        except Exception as error:
            failures += 1
            print(
                "{} | {} | ERROR: {}".format(
                    entry.symbol, entry.yahoo_symbol, error
                ),
                file=sys.stderr,
            )
            continue

        latest_date = pd.Timestamp(data.index[-1]).date().isoformat()
        print(
            "{} | {} | latest={} | OK".format(
                entry.symbol, entry.yahoo_symbol, latest_date
            )
        )

    return 1 if failures else 0


def _iso_date(value: str) -> datetime.date:
    try:
        return datetime.date.fromisoformat(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError(
            "Expected a date in YYYY-MM-DD format"
        ) from error


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--as-of",
        type=_iso_date,
        help="load the universe active on this date (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--universe",
        type=Path,
        default=helper.DEFAULT_UNIVERSE_PATH,
        help="path to an effective-dated BIST 30 CSV file",
    )
    parser.add_argument(
        "--validate-universe",
        action="store_true",
        help="check all configured Yahoo mappings without calculating RSI",
    )
    arguments = parser.parse_args(argv)

    try:
        universe = helper.load_bist30_universe(
            arguments.universe, arguments.as_of
        )
    except ValueError as error:
        print("UNIVERSE ERROR: {}".format(error), file=sys.stderr)
        return 1

    if arguments.validate_universe:
        return validate_provider_mappings(universe)

    failures = 0
    for entry in universe:
        try:
            result = scan_stock(
                entry.symbol, entry.yahoo_symbol, arguments.as_of
            )
        except Exception as error:
            failures += 1
            print("{} | ERROR: {}".format(entry.symbol, error), file=sys.stderr)
            continue

        session_date = pd.Timestamp(result.name).date().isoformat()
        close = float(result["Close"])
        rsi = float(result[RSI_COLUMN])
        status = "WARNING" if rsi < RSI_LOWER_BAND else "OK"
        print(
            "{} | date={} | adjusted_close={:.2f} | RSI({})={:.2f} | {}".format(
                entry.symbol, session_date, close, RSI_PERIOD, rsi, status
            )
        )

    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
