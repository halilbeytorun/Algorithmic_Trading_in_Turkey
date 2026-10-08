import csv
import datetime
import io
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

import pandas as pd

import helper
import main


UNIVERSE_FIELDNAMES = [
    "symbol",
    "yahoo_symbol",
    "effective_from",
    "effective_to",
    "retrieved_at",
    "source_url",
]


class UniverseTests(unittest.TestCase):
    def setUp(self):
        self.temp_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_directory.cleanup)

    def make_rows(self, count=30):
        return [
            {
                "symbol": "S{:02d}".format(index),
                "yahoo_symbol": "S{:02d}.IS".format(index),
                "effective_from": "2026-07-01",
                "effective_to": "2026-09-30",
                "retrieved_at": "2026-09-03",
                "source_url": "https://example.com/official-source.csv",
            }
            for index in range(count)
        ]

    def write_universe(self, rows, fieldnames=UNIVERSE_FIELDNAMES):
        path = Path(self.temp_directory.name) / "bist30.csv"
        with path.open("w", newline="", encoding="utf-8") as universe_file:
            writer = csv.DictWriter(
                universe_file, fieldnames=fieldnames, extrasaction="ignore"
            )
            writer.writeheader()
            writer.writerows(rows)
        return path

    def test_default_universe_contains_30_q3_mappings(self):
        universe = helper.load_bist30_universe(
            as_of_date=datetime.date(2026, 9, 3)
        )
        mappings = {entry.symbol: entry.yahoo_symbol for entry in universe}

        self.assertEqual(len(universe), 30)
        self.assertEqual(mappings["TRALT"], "TRALT.IS")
        self.assertEqual(mappings["DSTKF"], "DSTKF.IS")
        self.assertNotIn("TRMET", mappings)
        self.assertNotIn("KOZAL", mappings)
        self.assertNotIn("KOZAA", mappings)

    def test_default_universe_contains_30_q4_mappings(self):
        universe = helper.load_bist30_universe(
            as_of_date=datetime.date(2026, 10, 8)
        )
        mappings = {entry.symbol: entry.yahoo_symbol for entry in universe}

        self.assertEqual(len(universe), 30)
        self.assertEqual(mappings["TRMET"], "TRMET.IS")
        self.assertNotIn("DSTKF", mappings)
        self.assertTrue(
            all(
                entry.effective_from == datetime.date(2026, 10, 1)
                and entry.effective_to == datetime.date(2026, 12, 31)
                for entry in universe
            )
        )

    def test_universe_rejects_missing_column(self):
        fieldnames = [
            column for column in UNIVERSE_FIELDNAMES if column != "source_url"
        ]
        path = self.write_universe(self.make_rows(), fieldnames)

        with self.assertRaisesRegex(ValueError, "missing columns: source_url"):
            helper.load_bist30_universe(
                path, as_of_date=datetime.date(2026, 9, 3)
            )

    def test_universe_rejects_malformed_date(self):
        rows = self.make_rows()
        rows[0]["effective_from"] = "not-a-date"
        path = self.write_universe(rows)

        with self.assertRaisesRegex(ValueError, "invalid ISO date"):
            helper.load_bist30_universe(
                path, as_of_date=datetime.date(2026, 9, 3)
            )

    def test_universe_rejects_duplicate_symbol(self):
        rows = self.make_rows()
        rows[1]["symbol"] = rows[0]["symbol"]
        path = self.write_universe(rows)

        with self.assertRaisesRegex(ValueError, "duplicate BIST symbols: S00"):
            helper.load_bist30_universe(
                path, as_of_date=datetime.date(2026, 9, 3)
            )

    def test_universe_requires_exactly_30_active_entries(self):
        path = self.write_universe(self.make_rows(count=29))

        with self.assertRaisesRegex(ValueError, "found 29"):
            helper.load_bist30_universe(
                path, as_of_date=datetime.date(2026, 9, 3)
            )

    def test_universe_rejects_date_outside_effective_period(self):
        path = self.write_universe(self.make_rows())

        with self.assertRaisesRegex(ValueError, "found 0"):
            helper.load_bist30_universe(
                path, as_of_date=datetime.date(2026, 10, 1)
            )


class MarketDataTests(unittest.TestCase):
    def test_validation_preserves_close_and_volume(self):
        data = pd.DataFrame(
            {"Close": [325.0], "Volume": [41069874]},
            index=pd.to_datetime(["2026-08-14"]),
        )

        validated = helper.validate_stock_data(data, "THYAO", minimum_rows=1)

        self.assertEqual(validated.iloc[0]["Close"], 325.0)
        self.assertEqual(validated.iloc[0]["Volume"], 41069874)

    def test_validation_rejects_missing_volume(self):
        data = pd.DataFrame(
            {"Close": [325.0]}, index=pd.to_datetime(["2026-08-14"])
        )

        with self.assertRaisesRegex(ValueError, "missing columns: Volume"):
            helper.validate_stock_data(data, "THYAO", minimum_rows=1)

    def test_validation_drops_only_trailing_incomplete_row(self):
        data = pd.DataFrame(
            {"Close": [100.0, None], "Volume": [1000, 0]},
            index=pd.date_range("2026-01-01", periods=2, freq="D"),
        )

        validated = helper.validate_stock_data(data, "THYAO", minimum_rows=1)

        self.assertEqual(len(validated), 1)

    def test_usdtry_validation_rejects_interior_incomplete_row(self):
        data = pd.DataFrame(
            {"Close": [40.0, None, 41.0]},
            index=pd.date_range("2026-01-01", periods=3, freq="D"),
        )

        with self.assertRaisesRegex(ValueError, "inside its history"):
            helper.validate_usdtry_data(data, minimum_rows=1)

    @patch("helper.yf.Ticker")
    def test_download_uses_explicit_yahoo_mapping(self, ticker):
        data = pd.DataFrame(
            {
                "Close": range(100, 116),
                "Volume": range(1000, 1016),
            },
            index=pd.date_range("2026-01-01", periods=16, freq="D"),
        )
        ticker.return_value.history.return_value = data

        result = helper.download_stock_data("TRALT", "TRALT.IS")

        ticker.assert_called_once_with("TRALT.IS")
        ticker.return_value.history.assert_called_once_with(
            period="2y",
            interval="1d",
            auto_adjust=True,
            actions=False,
        )
        self.assertEqual(len(result), 16)

    @patch("helper.yf.Ticker")
    def test_download_usdtry_uses_try_per_dollar_mapping(self, ticker):
        data = pd.DataFrame(
            {"Close": [40.0, 41.0]},
            index=pd.date_range("2026-01-01", periods=2, freq="D"),
        )
        ticker.return_value.history.return_value = data

        result = helper.download_usdtry_data()

        ticker.assert_called_once_with("USDTRY=X")
        ticker.return_value.history.assert_called_once_with(
            period="5y",
            interval="1d",
            auto_adjust=False,
            actions=False,
        )
        self.assertEqual(result.tolist(), [40.0, 41.0])


class RsiTests(unittest.TestCase):
    def test_calculate_rsi_uses_wilder_smoothing(self):
        close = pd.Series([1.0, 2.0, 3.0, 2.0, 2.0, 4.0])

        rsi = main.calculate_rsi(close, period=3)

        self.assertTrue(rsi.iloc[:3].isna().all())
        self.assertAlmostEqual(rsi.iloc[3], 66.6666667, places=6)
        self.assertAlmostEqual(rsi.iloc[-1], 86.6666667, places=6)

    def test_flat_prices_have_neutral_rsi(self):
        rsi = main.calculate_rsi(pd.Series([10.0, 10.0, 10.0, 10.0]), period=3)

        self.assertEqual(rsi.iloc[-1], 50.0)

    def test_latest_completed_row_excludes_current_date(self):
        data = pd.DataFrame(
            {"Close": [100.0, 101.0], "RSI": [35.0, 30.0]},
            index=pd.to_datetime(["2026-08-14", "2026-08-17"]),
        )

        latest = main.latest_completed_row(
            data,
            as_of_date=datetime.date(2026, 8, 17),
            required_columns=["RSI"],
        )

        self.assertEqual(latest.name.date(), datetime.date(2026, 8, 14))


class CurrencyAnalysisTests(unittest.TestCase):
    def make_stock_data(self, close):
        index = pd.date_range("2025-01-01", periods=len(close), freq="D")
        return pd.DataFrame(
            {"Close": list(close), "Volume": [1000] * len(close)}, index=index
        )

    def test_fx_alignment_uses_previous_completed_rate(self):
        stock_index = pd.DatetimeIndex(
            ["2026-01-02", "2026-01-03"]
        ).tz_localize("Europe/Istanbul")
        fx = pd.Series(
            [40.0, 50.0],
            index=pd.DatetimeIndex(["2026-01-01", "2026-01-03"]).tz_localize(
                "Europe/London"
            ),
        )

        aligned = main.align_usdtry_to_stock_dates(stock_index, fx)

        self.assertEqual(aligned.tolist(), [40.0, 40.0])

    def test_fx_alignment_rejects_stale_rate(self):
        stock_index = pd.to_datetime(["2026-01-10"])
        fx = pd.Series([40.0], index=pd.to_datetime(["2026-01-01"]))

        with self.assertRaisesRegex(ValueError, "more than 7 days stale"):
            main.align_usdtry_to_stock_dates(stock_index, fx)

    def test_constant_fx_preserves_rsi_and_returns(self):
        close = pd.Series(
            [100.0 + index * 0.2 + (index % 5) for index in range(300)]
        )
        stock_data = self.make_stock_data(close)
        fx = pd.Series(
            40.0,
            index=pd.date_range(
                stock_data.index[0] - datetime.timedelta(days=1),
                periods=len(stock_data) + 1,
                freq="D",
            ),
        )

        analyzed = main.calculate_indicators(stock_data, fx)
        latest = analyzed.iloc[-1]

        self.assertAlmostEqual(latest["RSI_TRY"], latest["RSI_USD"], places=10)
        self.assertAlmostEqual(
            latest["RETURN_12M_TRY"], latest["RETURN_12M_USD"], places=10
        )
        self.assertAlmostEqual(
            latest["SMA200_TRY"] / 40.0, latest["SMA200_USD"], places=10
        )

    def test_try_depreciation_can_turn_try_gain_into_usd_loss(self):
        stock_data = self.make_stock_data(
            pd.Series([100.0 + index * 0.3 for index in range(300)])
        )
        fx = pd.Series(
            [20.0 + index * 0.12 for index in range(301)],
            index=pd.date_range(
                stock_data.index[0] - datetime.timedelta(days=1),
                periods=len(stock_data) + 1,
                freq="D",
            ),
        )

        latest = main.calculate_indicators(stock_data, fx).iloc[-1]

        self.assertGreater(latest["RETURN_12M_TRY"], 0)
        self.assertLess(latest["RETURN_12M_USD"], 0)

    @patch("main.helper.download_stock_data")
    def test_scan_uses_close_for_dual_currency_analysis(self, download_stock_data):
        stock_data = self.make_stock_data(
            pd.Series([100.0 + index for index in range(300)])
        )
        download_stock_data.return_value = stock_data
        fx = pd.Series(
            40.0,
            index=pd.date_range(
                stock_data.index[0] - datetime.timedelta(days=1),
                periods=len(stock_data) + 1,
                freq="D",
            ),
        )
        as_of_date = stock_data.index[-1].date() + datetime.timedelta(days=1)

        result = main.scan_stock("THYAO", "THYAO.IS", fx, as_of_date)

        download_stock_data.assert_called_once_with(
            "THYAO",
            "THYAO.IS",
            minimum_rows=254,
            start=as_of_date - datetime.timedelta(days=730),
            end=as_of_date,
        )
        self.assertEqual(result.rsi_try, 100.0)
        self.assertEqual(result.rsi_usd, 100.0)
        self.assertEqual(result.status, "TRY_AND_USD_UPTREND")


class ClassificationTests(unittest.TestCase):
    def test_classification_priorities(self):
        cases = [
            (
                (True, True, 35.0, 31.0, 30.0),
                "USD_RECOVERY_CANDIDATE",
            ),
            ((True, True, 35.0, 30.0, 29.0), "USD_PULLBACK_WATCH"),
            ((True, True, 35.0, 35.0, 36.0), "USD_PULLBACK_WATCH"),
            ((True, True, 55.0, 55.0, 54.0), "TRY_AND_USD_UPTREND"),
            ((True, False, 55.0, 55.0, 54.0), "TRY_ONLY_UPTREND"),
            ((False, True, 55.0, 55.0, 54.0), "USD_ONLY_UPTREND"),
            ((False, False, 35.0, 45.0, 46.0), "LOW_RSI_WITHOUT_UPTREND"),
            ((False, False, 55.0, 55.0, 54.0), "NO_CONFIRMED_UPTREND"),
        ]

        for arguments, expected in cases:
            with self.subTest(expected=expected):
                self.assertEqual(main.classify_setup(*arguments), expected)


class ProviderValidationTests(unittest.TestCase):
    @patch("main.helper.download_usdtry_data")
    @patch("main.helper.download_stock_data")
    def test_provider_validation_uses_configured_mappings(
        self, download_stock_data, download_usdtry_data
    ):
        download_stock_data.return_value = pd.DataFrame(
            {"Close": [100.0], "Volume": [1000]},
            index=pd.to_datetime(["2026-09-02"]),
        )
        download_usdtry_data.return_value = pd.Series(
            [40.0], index=pd.to_datetime(["2026-09-02"])
        )
        entry = helper.UniverseEntry(
            symbol="TRALT",
            yahoo_symbol="TRALT.IS",
            effective_from=datetime.date(2026, 7, 1),
            effective_to=datetime.date(2026, 9, 30),
            retrieved_at=datetime.date(2026, 9, 3),
            source_url="https://example.com/official-source.csv",
        )

        with redirect_stdout(io.StringIO()):
            status = main.validate_provider_mappings([entry])

        self.assertEqual(status, 0)
        download_stock_data.assert_called_once_with(
            "TRALT", "TRALT.IS", period="5d", minimum_rows=1
        )
        download_usdtry_data.assert_called_once_with(
            period="5d", minimum_rows=1
        )


class DateValidationTests(unittest.TestCase):
    def test_future_as_of_date_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "cannot be later"):
            main.validate_as_of_date(
                datetime.date(2026, 10, 9),
                today=datetime.date(2026, 10, 8),
            )

    def test_today_is_allowed_because_today_bar_is_excluded(self):
        main.validate_as_of_date(
            datetime.date(2026, 10, 8),
            today=datetime.date(2026, 10, 8),
        )


if __name__ == "__main__":
    unittest.main()
