"""Download and validate market data used by the stock screener."""

import math

import pandas as pd
import yfinance as yf


# BIST 30 candidate list. This static list currently contains 29 stocks.
bist30_stock_list = [
    "THYAO",
    "AKBNK",
    "ARCLK",
    "ASELS",
    "BIMAS",
    "DOHOL",
    "EKGYO",
    "EREGL",
    "GUBRF",
    "GARAN",
    "KRDMD",
    "KCHOL",
    "KOZAL",
    "KOZAA",
    "PGSUS",
    "PETKM",
    "SAHOL",
    "SASA",
    "SISE",
    "TAVHL",
    "TKFEN",
    "TUPRS",
    "TTKOM",
    "TCELL",
    "HALKB",
    "ISCTR",
    "VAKBN",
    "VESTL",
    "YKBNK",
]


def validate_stock_data(
    data: pd.DataFrame, stock_name: str, minimum_rows: int = 16
) -> pd.DataFrame:
    """Validate and normalize the market data needed by the RSI scanner."""
    if not isinstance(data, pd.DataFrame) or data.empty:
        raise ValueError("{} returned no market data".format(stock_name))

    required_columns = {"Close", "Volume"}
    missing_columns = required_columns.difference(data.columns)
    if missing_columns:
        raise ValueError(
            "{} data is missing columns: {}".format(
                stock_name, ", ".join(sorted(missing_columns))
            )
        )
    if len(data) < minimum_rows:
        raise ValueError(
            "{} returned {} rows; at least {} are required".format(
                stock_name, len(data), minimum_rows
            )
        )

    validated = data.copy()
    try:
        validated.index = pd.DatetimeIndex(pd.to_datetime(validated.index))
    except (TypeError, ValueError) as error:
        raise ValueError("{} has an invalid date index".format(stock_name)) from error

    if validated.index.has_duplicates:
        raise ValueError("{} data contains duplicate dates".format(stock_name))
    validated = validated.sort_index()

    close = pd.to_numeric(validated["Close"], errors="coerce")
    volume = pd.to_numeric(validated["Volume"], errors="coerce")
    if close.isna().any() or not close.map(math.isfinite).all():
        raise ValueError("{} closing prices contain invalid values".format(stock_name))
    if volume.isna().any() or not volume.map(math.isfinite).all():
        raise ValueError("{} volumes contain invalid values".format(stock_name))
    if (close <= 0).any():
        raise ValueError("{} closing prices must be positive".format(stock_name))
    if (volume < 0).any():
        raise ValueError("{} volumes cannot be negative".format(stock_name))

    validated["Close"] = close.astype(float)
    validated["Volume"] = volume
    return validated


def download_stock_data(
    target_stock_name: str, period: str = "250d", minimum_rows: int = 16
) -> pd.DataFrame:
    """Download adjusted daily prices and return a validated DataFrame."""
    provider_symbol = target_stock_name + ".IS"
    data = yf.Ticker(provider_symbol).history(
        period=period,
        interval="1d",
        auto_adjust=True,
        actions=False,
    )
    return validate_stock_data(data, target_stock_name, minimum_rows)
