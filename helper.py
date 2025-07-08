# Will be having helper functions like saving data
import os
import yfinance as yf


# Bist 30
bist30_stock_list = ['THYAO', 'AKBNK', 'ARCLK', 'ASELS', 'BIMAS', 'DOHOL', 'EKGYO', 'EREGL'
, 'GUBRF', 'GARAN', 'KRDMD', 'KCHOL', 'KOZAL', 'KOZAA', 'PGSUS', 'PETKM', 'SAHOL'
, 'SASA', 'SISE', 'TAVHL', 'TKFEN', 'TUPRS', 'TTKOM', 'TCELL', 'HALKB', 'ISCTR', 'VAKBN'
, 'VESTL', 'YKBNK'
]

def save_stock_to_csv(
    target_stock_name: str,
    abs_path_to_data_dir: str,
    period: str = "50d",
    interval: str = "1d"
):
    '''
    Saves the stock given to a csv file under data folder.
    Creates the directory if it does not exist.
    If the file already exists, it will be overwritten.
    '''
    # Ensure the directory exists
    if not os.path.exists(abs_path_to_data_dir):
        os.makedirs(abs_path_to_data_dir)

    target_stock = yf.Ticker(target_stock_name + '.IS')
    target_stock_hist_data = target_stock.history(period=period, interval=interval)
    target_stock_hist_data.to_csv(os.path.join(abs_path_to_data_dir, target_stock_name + '.csv'))
