# Will be having helper functions like saving data
import yfinance as yf


# Bist 30
bist30_stock_list = ['THYAO', 'AKBNK', 'ARCLK', 'ASELS', 'BIMAS', 'DOHOL', 'EKGYO', 'EREGL'
, 'GUBRF', 'GARAN', 'KRDMD', 'KCHOL', 'KOZAL', 'KOZAA', 'PGSUS', 'PETKM', 'SAHOL'
, 'SASA', 'SISE', 'TAVHL', 'TKFEN', 'TUPRS', 'TTKOM', 'TCELL', 'HALKB', 'ISCTR', 'VAKBN'
, 'VESTL', 'YKBNK'
]


def save_stock_to_csv(target_stock_name: str):
    '''
    Saves the stock given to a csv file under data folder
    '''
    target_stock = yf.Ticker(target_stock_name + '.IS')
    target_stock_hist_data = target_stock.history(period="50d", interval="1d")

    target_stock_hist_data.to_csv("./data/" + target_stock_name + '.csv')
