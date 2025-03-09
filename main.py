# Will have the main functions
from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import datetime
import os.path
import sys

import backtrader as bt
import helper

# import debugpy
# debugpy.listen(5678)
# debugpy.wait_for_client()  # blocks execution until client is attached



# Create a Stratey
class TestStrategy(bt.Strategy):
    params = (
    ('rsi_period', 15), ('rsi_lower_band', 35), ('rsi_upper_band', 67), ('exitbars', 5)
    )
    def __init__(self):
        # Keep a reference to the "close" line in the data[0] dataseries
        self.dataclose = self.datas[0].close

        # Add a Relative Strength Index (RSI)   
        self.rsi = bt.indicators.RelativeStrengthIndex(self.datas[0], period = self.params.rsi_period, lowerband=self.params.rsi_lower_band, upperband=self.params.rsi_upper_band)  # todo how does it work like that?


    def next(self):
        if(self.datas[0].datetime.date(0) > (datetime.datetime.now().date() - datetime.timedelta(days=3))): # TODO
            if self.rsi[0] < self.rsi.params.lowerband: #Send the warning! Here
                print("-----------------------------------------WARNING------------------------------------")



if __name__ == '__main__':

    for name in helper.bist30_stock_list:
        print(name)

        helper.save_stock_to_csv(name)

        cerebro = bt.Cerebro()

        cerebro.addstrategy(TestStrategy)

        modpath = os.path.dirname(os.path.abspath(sys.argv[0]))
        datapath = os.path.join(modpath, './data/' + name+'.csv')

        data = bt.feeds.YahooFinanceCSVData(
            dataname=datapath,
            reverse=False
            )

        # Add the Data Feed to Cerebro
        cerebro.adddata(data)

        # Set our desired cash start
        cerebro.broker.setcash(100000.0)

        # Add a FixedSize suzer according to the stake
        cerebro.addsizer(bt.sizers.FixedSize, stake=10)

        # Set the commission - 0.1% ... divide by 100 to remove the %
        cerebro.broker.setcommission(commission=0.001)

        # Print out the starting conditions
        print('Starting Portfolio Value: %.2f' % cerebro.broker.getvalue())

        # Run over everything
        cerebro.run()

        # Print out the final result
        print('Final Portfolio Value: %.2f' % cerebro.broker.getvalue())


