"""Scan BIST 30 stocks using TRY and USD-adjusted long-term indicators."""

import argparse
import datetime
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Sequence, Tuple

import pandas as pd

import helper


RSI_PERIOD = 15
RSI_LOWER_BAND = 40.0
RSI_OVERSOLD_BAND = 30.0
SMA_MEDIUM_PERIOD = 50
SMA_LONG_PERIOD = 200
SMA_TREND_LOOKBACK = 20
RETURN_12M_PERIOD = 252
MINIMUM_HISTORY_ROWS = RETURN_12M_PERIOD + 2
MAX_FX_STALENESS_DAYS = 7
HISTORY_WINDOW_DAYS = 730
FX_HISTORY_HEADSTART_DAYS = 14

REQUIRED_ANALYSIS_COLUMNS = (
    "USDTRY",
    "Close_USD",
    "RSI_TRY",
    "RSI_USD",
    "RSI_USD_PREVIOUS",
    "SMA50_TRY",
    "SMA200_TRY",
    "SMA200_TRY_PREVIOUS",
    "SMA50_USD",
    "SMA200_USD",
    "SMA200_USD_PREVIOUS",
    "RETURN_12M_TRY",
    "RETURN_12M_USD",
)


@dataclass(frozen=True)
class StockAnalysis:
    symbol: str
    session_date: datetime.date
    close_try: float
    close_usd: float
    usdtry: float
    rsi_try: float
    rsi_usd: float
    sma50_try: float
    sma200_try: float
    sma50_usd: float
    sma200_usd: float
    return_12m_try: float
    return_12m_usd: float
    try_uptrend: bool
    usd_uptrend: bool
    status: str


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
    rsi = pd.Series(index=prices.index, dtype="float64", name="RSI")
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


def _local_session_dates(index: pd.Index) -> pd.DatetimeIndex:
    dates = pd.DatetimeIndex(pd.to_datetime(index))
    if dates.tz is not None:
        dates = dates.tz_localize(None)
    return dates.normalize()


def align_usdtry_to_stock_dates(
    stock_index: pd.Index, usdtry: pd.Series
) -> pd.Series:
    """Align each stock date with an FX close completed before that date."""
    if usdtry.empty:
        raise ValueError("Cannot convert prices without USD/TRY data")

    stock_dates = _local_session_dates(stock_index)
    fx_dates = _local_session_dates(usdtry.index)
    if stock_dates.has_duplicates:
        raise ValueError("Stock data contains duplicate session dates")
    if fx_dates.has_duplicates:
        raise ValueError("USD/TRY data contains duplicate session dates")

    fx_values = pd.to_numeric(usdtry, errors="coerce").astype(float)
    if fx_values.isna().any() or (fx_values <= 0).any():
        raise ValueError("USD/TRY rates must be positive numeric values")

    availability_dates = fx_dates + pd.Timedelta(days=1)
    fx_by_date = pd.Series(
        fx_values.to_numpy(), index=availability_dates, name="USDTRY"
    ).sort_index()
    fx_source_dates = pd.Series(
        fx_dates, index=availability_dates
    ).sort_index()
    aligned_values = fx_by_date.reindex(stock_dates, method="ffill")
    aligned_source_dates = fx_source_dates.reindex(stock_dates, method="ffill")

    if aligned_values.isna().any() or aligned_source_dates.isna().any():
        raise ValueError("USD/TRY data does not cover the stock price history")

    source_dates = pd.DatetimeIndex(aligned_source_dates.to_numpy())
    staleness_days = (stock_dates - source_dates).days
    if (staleness_days < 0).any():
        raise ValueError("USD/TRY alignment attempted to use a future rate")
    if (staleness_days > MAX_FX_STALENESS_DAYS).any():
        raise ValueError(
            "USD/TRY data is more than {} days stale".format(
                MAX_FX_STALENESS_DAYS
            )
        )

    return pd.Series(
        aligned_values.to_numpy(), index=stock_index, name="USDTRY"
    )


def calculate_indicators(
    stock_data: pd.DataFrame, usdtry: pd.Series
) -> pd.DataFrame:
    """Calculate TRY and USD momentum, trend, and return indicators."""
    analyzed = stock_data.copy()
    analyzed["USDTRY"] = align_usdtry_to_stock_dates(analyzed.index, usdtry)
    analyzed["Close_USD"] = analyzed["Close"] / analyzed["USDTRY"]

    analyzed["RSI_TRY"] = calculate_rsi(analyzed["Close"], RSI_PERIOD)
    analyzed["RSI_USD"] = calculate_rsi(analyzed["Close_USD"], RSI_PERIOD)
    analyzed["RSI_USD_PREVIOUS"] = analyzed["RSI_USD"].shift(1)

    analyzed["SMA50_TRY"] = analyzed["Close"].rolling(SMA_MEDIUM_PERIOD).mean()
    analyzed["SMA200_TRY"] = analyzed["Close"].rolling(SMA_LONG_PERIOD).mean()
    analyzed["SMA200_TRY_PREVIOUS"] = analyzed["SMA200_TRY"].shift(
        SMA_TREND_LOOKBACK
    )
    analyzed["SMA50_USD"] = analyzed["Close_USD"].rolling(
        SMA_MEDIUM_PERIOD
    ).mean()
    analyzed["SMA200_USD"] = analyzed["Close_USD"].rolling(
        SMA_LONG_PERIOD
    ).mean()
    analyzed["SMA200_USD_PREVIOUS"] = analyzed["SMA200_USD"].shift(
        SMA_TREND_LOOKBACK
    )

    analyzed["RETURN_12M_TRY"] = analyzed["Close"].pct_change(
        RETURN_12M_PERIOD, fill_method=None
    )
    analyzed["RETURN_12M_USD"] = analyzed["Close_USD"].pct_change(
        RETURN_12M_PERIOD, fill_method=None
    )
    return analyzed


def latest_completed_row(
    data: pd.DataFrame,
    as_of_date: Optional[datetime.date] = None,
    required_columns: Sequence[str] = (),
) -> pd.Series:
    """Return the latest complete row with all required indicator values."""
    if data.empty:
        raise ValueError("Cannot select a completed row from empty data")

    if as_of_date is None:
        as_of_date = pd.Timestamp.now(tz="Europe/Istanbul").date()

    index = pd.DatetimeIndex(pd.to_datetime(data.index))
    if index.tz is not None:
        index = index.tz_convert("Europe/Istanbul")

    completed = data.loc[index.date < as_of_date]
    if required_columns:
        missing_columns = set(required_columns).difference(completed.columns)
        if missing_columns:
            raise ValueError(
                "Analysis is missing columns: {}".format(
                    ", ".join(sorted(missing_columns))
                )
            )
        completed = completed.dropna(subset=list(required_columns))
    if completed.empty:
        raise ValueError("No completed session with calculated indicators is available")

    return completed.sort_index().iloc[-1]


def _long_term_trends(row: pd.Series) -> Tuple[bool, bool]:
    try_uptrend = bool(
        row["Close"] > row["SMA200_TRY"]
        and row["SMA50_TRY"] > row["SMA200_TRY"]
        and row["SMA200_TRY"] > row["SMA200_TRY_PREVIOUS"]
    )
    usd_uptrend = bool(
        row["Close_USD"] > row["SMA200_USD"]
        and row["SMA50_USD"] > row["SMA200_USD"]
        and row["SMA200_USD"] > row["SMA200_USD_PREVIOUS"]
    )
    return try_uptrend, usd_uptrend


def classify_setup(
    try_uptrend: bool,
    usd_uptrend: bool,
    rsi_try: float,
    rsi_usd: float,
    previous_rsi_usd: float,
) -> str:
    """Classify the setup without presenting it as investment advice."""
    if (
        usd_uptrend
        and previous_rsi_usd <= RSI_OVERSOLD_BAND
        and rsi_usd > RSI_OVERSOLD_BAND
    ):
        return "USD_RECOVERY_CANDIDATE"
    if usd_uptrend and rsi_usd < RSI_LOWER_BAND:
        return "USD_PULLBACK_WATCH"
    if try_uptrend and usd_uptrend:
        return "TRY_AND_USD_UPTREND"
    if try_uptrend and not usd_uptrend:
        return "TRY_ONLY_UPTREND"
    if usd_uptrend and not try_uptrend:
        return "USD_ONLY_UPTREND"
    if rsi_try < RSI_LOWER_BAND or rsi_usd < RSI_LOWER_BAND:
        return "LOW_RSI_WITHOUT_UPTREND"
    return "NO_CONFIRMED_UPTREND"


def scan_stock(
    stock_name: str,
    yahoo_symbol: str,
    usdtry: pd.Series,
    as_of_date: Optional[datetime.date] = None,
) -> StockAnalysis:
    if as_of_date is None:
        as_of_date = pd.Timestamp.now(tz="Europe/Istanbul").date()
    history_start = as_of_date - datetime.timedelta(days=HISTORY_WINDOW_DAYS)
    data = helper.download_stock_data(
        stock_name,
        yahoo_symbol,
        minimum_rows=MINIMUM_HISTORY_ROWS,
        start=history_start,
        end=as_of_date,
    )
    analyzed = calculate_indicators(data, usdtry)
    latest = latest_completed_row(
        analyzed, as_of_date, REQUIRED_ANALYSIS_COLUMNS
    )
    try_uptrend, usd_uptrend = _long_term_trends(latest)
    status = classify_setup(
        try_uptrend,
        usd_uptrend,
        float(latest["RSI_TRY"]),
        float(latest["RSI_USD"]),
        float(latest["RSI_USD_PREVIOUS"]),
    )

    return StockAnalysis(
        symbol=stock_name,
        session_date=pd.Timestamp(latest.name).date(),
        close_try=float(latest["Close"]),
        close_usd=float(latest["Close_USD"]),
        usdtry=float(latest["USDTRY"]),
        rsi_try=float(latest["RSI_TRY"]),
        rsi_usd=float(latest["RSI_USD"]),
        sma50_try=float(latest["SMA50_TRY"]),
        sma200_try=float(latest["SMA200_TRY"]),
        sma50_usd=float(latest["SMA50_USD"]),
        sma200_usd=float(latest["SMA200_USD"]),
        return_12m_try=float(latest["RETURN_12M_TRY"]),
        return_12m_usd=float(latest["RETURN_12M_USD"]),
        try_uptrend=try_uptrend,
        usd_uptrend=usd_uptrend,
        status=status,
    )


def validate_provider_mappings(
    universe: Sequence[helper.UniverseEntry],
) -> int:
    """Check that all configured stock and FX symbols return market data."""
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

    try:
        usdtry = helper.download_usdtry_data(period="5d", minimum_rows=1)
    except Exception as error:
        failures += 1
        print(
            "USDTRY | {} | ERROR: {}".format(
                helper.USDTRY_YAHOO_SYMBOL, error
            ),
            file=sys.stderr,
        )
    else:
        latest_date = pd.Timestamp(usdtry.index[-1]).date().isoformat()
        print(
            "USDTRY | {} | latest={} | OK".format(
                helper.USDTRY_YAHOO_SYMBOL, latest_date
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


def validate_as_of_date(
    as_of_date: Optional[datetime.date],
    today: Optional[datetime.date] = None,
) -> None:
    """Reject cutoffs that could include current or future incomplete data."""
    if as_of_date is None:
        return
    if today is None:
        today = pd.Timestamp.now(tz="Europe/Istanbul").date()
    if as_of_date > today:
        raise ValueError(
            "Analysis date {} cannot be later than {}".format(
                as_of_date.isoformat(), today.isoformat()
            )
        )


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--as-of",
        type=_iso_date,
        help="analyze sessions before this date using its active universe",
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
        help="check all configured Yahoo mappings without calculating indicators",
    )
    arguments = parser.parse_args(argv)

    today = pd.Timestamp.now(tz="Europe/Istanbul").date()
    try:
        validate_as_of_date(arguments.as_of, today)
    except ValueError as error:
        print("DATE ERROR: {}".format(error), file=sys.stderr)
        return 1
    analysis_date = arguments.as_of or today

    try:
        universe = helper.load_bist30_universe(
            arguments.universe, analysis_date
        )
    except ValueError as error:
        print("UNIVERSE ERROR: {}".format(error), file=sys.stderr)
        return 1

    if arguments.validate_universe:
        return validate_provider_mappings(universe)

    stock_history_start = analysis_date - datetime.timedelta(
        days=HISTORY_WINDOW_DAYS
    )
    fx_history_start = stock_history_start - datetime.timedelta(
        days=FX_HISTORY_HEADSTART_DAYS
    )
    try:
        usdtry = helper.download_usdtry_data(
            minimum_rows=MINIMUM_HISTORY_ROWS,
            start=fx_history_start,
            end=analysis_date,
        )
    except Exception as error:
        print("FX ERROR: {}".format(error), file=sys.stderr)
        return 1

    failures = 0
    for entry in universe:
        try:
            result = scan_stock(
                entry.symbol,
                entry.yahoo_symbol,
                usdtry,
                analysis_date,
            )
        except Exception as error:
            failures += 1
            print("{} | ERROR: {}".format(entry.symbol, error), file=sys.stderr)
            continue

        print(
            "{} | date={} | USDTRY={:.4f} | "
            "TRY close={:.2f} RSI15={:.2f} SMA50={:.2f} SMA200={:.2f} 12m={:+.2%} | "
            "USD close={:.2f} RSI15={:.2f} SMA50={:.2f} SMA200={:.2f} 12m={:+.2%} | "
            "trend TRY={} USD={} | {}".format(
                result.symbol,
                result.session_date.isoformat(),
                result.usdtry,
                result.close_try,
                result.rsi_try,
                result.sma50_try,
                result.sma200_try,
                result.return_12m_try,
                result.close_usd,
                result.rsi_usd,
                result.sma50_usd,
                result.sma200_usd,
                result.return_12m_usd,
                "UP" if result.try_uptrend else "NOT_UP",
                "UP" if result.usd_uptrend else "NOT_UP",
                result.status,
            )
        )

    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
