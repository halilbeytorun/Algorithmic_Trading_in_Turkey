import datetime
import unittest
from unittest.mock import patch

import pandas as pd

import helper
import main


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
    def test_download_requests_adjusted_daily_data(self, ticker):
        data = pd.DataFrame(
            {
                "Close": range(100, 116),
                "Volume": range(1000, 1016),
            },
            index=pd.date_range("2026-01-01", periods=16, freq="D"),
        )
        ticker.return_value.history.return_value = data

        result = helper.download_stock_data("THYAO")

        ticker.assert_called_once_with("THYAO.IS")
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

        result = main.scan_stock("THYAO", as_of_date=datetime.date(2026, 1, 18))

        download_stock_data.assert_called_once_with("THYAO", minimum_rows=16)
        self.assertEqual(result["Close"], 116.0)
        self.assertEqual(result["RSI"], 100.0)


if __name__ == "__main__":
    unittest.main()
