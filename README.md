# Algorithmic_Trading_in_Turkey
## Abstract
Gets Turkiye's BIST30 stock markets and saves them under provided data path subfolder. Then uses those stock market values to calculate RSI values for the current date and reports if it is below some value (35 atm)

## How to use
Easiest way to use this project is
* Create a virtual environment and use it
```
python -m venv venv
source venv/bin/activate
```

* Install necessary dependencies
```
pip install -r requirements.txt
```

* Call python interpreter
```
python main.py
```

## Dependencies
* python3.7
* yfinance
* backtrader
* requests
