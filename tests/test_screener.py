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
            period="250d",
            interval="1d",
            auto_adjust=True,
            actions=False,
        )
        self.assertEqual(len(result), 16)


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
            {"Close": [100.0, 101.0], "Volume": [1000, 1100], "RSI": [35.0, 30.0]},
            index=pd.to_datetime(["2026-08-14", "2026-08-17"]),
        )

        latest = main.latest_completed_row(
            data, as_of_date=datetime.date(2026, 8, 17)
        )

        self.assertEqual(latest.name.date(), datetime.date(2026, 8, 14))

    @patch("main.helper.download_stock_data")
    def test_scan_calculates_rsi_from_close_not_volume(self, download_stock_data):
        download_stock_data.return_value = pd.DataFrame(
            {
                "Close": range(100, 117),
                "Volume": range(1016, 999, -1),
            },
            index=pd.date_range("2026-01-01", periods=17, freq="D"),
        )

        result = main.scan_stock(
            "THYAO", "THYAO.IS", as_of_date=datetime.date(2026, 1, 18)
        )

        download_stock_data.assert_called_once_with(
            "THYAO", "THYAO.IS", minimum_rows=16
        )
        self.assertEqual(result["Close"], 116.0)
        self.assertEqual(result["RSI"], 100.0)


class ProviderValidationTests(unittest.TestCase):
    @patch("main.helper.download_stock_data")
    def test_provider_validation_uses_configured_mapping(self, download_stock_data):
        download_stock_data.return_value = pd.DataFrame(
            {"Close": [100.0], "Volume": [1000]},
            index=pd.to_datetime(["2026-09-02"]),
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


if __name__ == "__main__":
    unittest.main()
