"""Scan BIST stocks for a low Relative Strength Index (RSI)."""

import datetime
import sys
from typing import Optional

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
    stock_name: str, as_of_date: Optional[datetime.date] = None
) -> pd.Series:
    data = helper.download_stock_data(stock_name, minimum_rows=RSI_PERIOD + 1)
    analyzed = data.copy()
    analyzed[RSI_COLUMN] = calculate_rsi(analyzed["Close"], RSI_PERIOD)
    return latest_completed_row(analyzed, as_of_date)


def main() -> int:
    failures = 0

    for stock_name in helper.bist30_stock_list:
        try:
            result = scan_stock(stock_name)
        except Exception as error:
            failures += 1
            print("{} | ERROR: {}".format(stock_name, error), file=sys.stderr)
            continue

        session_date = pd.Timestamp(result.name).date().isoformat()
        close = float(result["Close"])
        rsi = float(result[RSI_COLUMN])
        status = "WARNING" if rsi < RSI_LOWER_BAND else "OK"
        print(
            "{} | date={} | adjusted_close={:.2f} | RSI({})={:.2f} | {}".format(
                stock_name, session_date, close, RSI_PERIOD, rsi, status
            )
        )

    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
