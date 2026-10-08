"""Load the BIST 30 universe and download validated market data."""

import csv
import datetime
import math
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

import pandas as pd
import yfinance as yf


EXPECTED_UNIVERSE_SIZE = 30
DEFAULT_UNIVERSE_PATH = Path(__file__).resolve().parent / "config" / "bist30.csv"
UNIVERSE_COLUMNS = {
    "symbol",
    "yahoo_symbol",
    "effective_from",
    "effective_to",
    "retrieved_at",
    "source_url",
}
SYMBOL_PATTERN = re.compile(r"^[A-Z0-9]+$")
YAHOO_SYMBOL_PATTERN = re.compile(r"^[A-Z0-9]+\.IS$")


@dataclass(frozen=True)
class UniverseEntry:
    symbol: str
    yahoo_symbol: str
    effective_from: datetime.date
    effective_to: datetime.date
    retrieved_at: datetime.date
    source_url: str


def load_bist30_universe(
    path: Optional[Path] = None,
    as_of_date: Optional[datetime.date] = None,
) -> List[UniverseEntry]:
    """Load and validate the 30 constituents active on ``as_of_date``."""
    universe_path = Path(path) if path is not None else DEFAULT_UNIVERSE_PATH
    if as_of_date is None:
        as_of_date = pd.Timestamp.now(tz="Europe/Istanbul").date()

    try:
        universe_file = universe_path.open(newline="", encoding="utf-8")
    except OSError as error:
        raise ValueError(
            "Cannot read BIST 30 universe file {}: {}".format(universe_path, error)
        ) from error

    with universe_file:
        reader = csv.DictReader(universe_file)
        fieldnames = reader.fieldnames or []
        missing_columns = UNIVERSE_COLUMNS.difference(fieldnames)
        if missing_columns:
            raise ValueError(
                "Universe file is missing columns: {}".format(
                    ", ".join(sorted(missing_columns))
                )
            )
        if len(fieldnames) != len(set(fieldnames)):
            raise ValueError("Universe file contains duplicate column names")

        active_entries = []
        for row_number, row in enumerate(reader, start=2):
            if None in row:
                raise ValueError(
                    "Universe row {} has more values than columns".format(row_number)
                )

            values = {
                column: (row.get(column) or "").strip()
                for column in UNIVERSE_COLUMNS
            }
            empty_columns = [
                column for column, value in values.items() if not value
            ]
            if empty_columns:
                raise ValueError(
                    "Universe row {} has empty columns: {}".format(
                        row_number, ", ".join(sorted(empty_columns))
                    )
                )

            if not SYMBOL_PATTERN.fullmatch(values["symbol"]):
                raise ValueError(
                    "Universe row {} has invalid BIST symbol {}".format(
                        row_number, values["symbol"]
                    )
                )
            if not YAHOO_SYMBOL_PATTERN.fullmatch(values["yahoo_symbol"]):
                raise ValueError(
                    "Universe row {} has invalid Yahoo symbol {}".format(
                        row_number, values["yahoo_symbol"]
                    )
                )
            if not values["source_url"].startswith("https://"):
                raise ValueError(
                    "Universe row {} must have an HTTPS source URL".format(row_number)
                )

            try:
                effective_from = datetime.date.fromisoformat(
                    values["effective_from"]
                )
                effective_to = datetime.date.fromisoformat(values["effective_to"])
                retrieved_at = datetime.date.fromisoformat(values["retrieved_at"])
            except ValueError as error:
                raise ValueError(
                    "Universe row {} contains an invalid ISO date".format(row_number)
                ) from error

            if effective_from > effective_to:
                raise ValueError(
                    "Universe row {} has an invalid effective date range".format(
                        row_number
                    )
                )

            if effective_from <= as_of_date <= effective_to:
                active_entries.append(
                    UniverseEntry(
                        symbol=values["symbol"],
                        yahoo_symbol=values["yahoo_symbol"],
                        effective_from=effective_from,
                        effective_to=effective_to,
                        retrieved_at=retrieved_at,
                        source_url=values["source_url"],
                    )
                )

    if len(active_entries) != EXPECTED_UNIVERSE_SIZE:
        raise ValueError(
            "Expected {} active BIST 30 constituents on {}, found {} in {}".format(
                EXPECTED_UNIVERSE_SIZE,
                as_of_date.isoformat(),
                len(active_entries),
                universe_path,
            )
        )

    duplicate_symbols = sorted(
        symbol
        for symbol, count in Counter(
            entry.symbol for entry in active_entries
        ).items()
        if count > 1
    )
    if duplicate_symbols:
        raise ValueError(
            "Universe contains duplicate BIST symbols: {}".format(
                ", ".join(duplicate_symbols)
            )
        )

    duplicate_yahoo_symbols = sorted(
        symbol
        for symbol, count in Counter(
            entry.yahoo_symbol for entry in active_entries
        ).items()
        if count > 1
    )
    if duplicate_yahoo_symbols:
        raise ValueError(
            "Universe contains duplicate Yahoo symbols: {}".format(
                ", ".join(duplicate_yahoo_symbols)
            )
        )

    return active_entries


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
    stock_name: str,
    yahoo_symbol: str,
    period: str = "250d",
    minimum_rows: int = 16,
) -> pd.DataFrame:
    """Download adjusted daily prices and return a validated DataFrame."""
    data = yf.Ticker(yahoo_symbol).history(
        period=period,
        interval="1d",
        auto_adjust=True,
        actions=False,
    )
    return validate_stock_data(data, stock_name, minimum_rows)
