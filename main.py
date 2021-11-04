# Will have the main functions

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import datetime  # For datetime objects
import os.path  # To manage paths
import sys  # To find out the script name (in argv[0])

# Import the backtrader platform
import backtrader as bt
import helper

'''
Things to note:
crebro
    broker
    data feed

'''

global_stock_name = 'NAK'

#total = 0.0

# Create a Stratey
class TestStrategy(bt.Strategy):
    params = (
    ('maperiod', 15), ('my_lower_band', 35), ('my_upper_band', 67), ('exitbars', 5)
    )
    def log(self, txt, dt=None):
        ''' Logging function for this strategy'''
        dt = dt or self.datas[0].datetime.date(0)
        print('%s, %s' % (dt.isoformat(), txt))

    def __init__(self):
        # Keep a reference to the "close" line in the data[0] dataseries
        self.dataclose = self.datas[0].close

        # To keep track of pending orders and buy price/commissions
        self.order = None
        self.buyprice = None
        self.buycomm = None

        # Add a Relative Strength Index (RSI)   
        self.rsi = bt.indicators.RelativeStrengthIndex(self.datas[0], period = self.params.maperiod, lowerband=self.params.my_lower_band, upperband=self.params.my_upper_band)  # todo how does it work like that?

    def notify_order(self, order):
        if order.status in [order.Submitted, order.Accepted]:
            return

        #Check if an order has ben completed
        # Attention: broker could reject order if not enough cash
        if order.status in [order.Completed]:
            if order.isbuy():
                self.log('BUY EXECUTED, Price: %.2f, Cost: %.2f, Comm: %.2f' %(order.executed.price, order.executed.value, order.executed.comm))
                self.buyprice = order.executed.price
                self.buycomm = order.executed.comm

            elif order.issell():
                self.log('SELL EXECUTED, Price: %.2f, Cost: %.2f, Comm: %.2f' %(order.executed.price, order.executed.value, order.executed.comm))
            self.bar_executed = len(self)

        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            self.log('Order Canceled/Margin/Rejected')
        
        self.order = None   # Reset the order after notification
    
    def notify_trade(self, trade):
        if not trade.isclosed:
            return
        
        self.log('OPERATION PROFIT, GROSS %.2f, NET %.2f' % (trade.pnl, trade.pnlcomm))

        #global total
        #total += trade.pnlcomm

    def next(self):
        # Simply log the closing price of the series from the reference
        #self.log('Close, %.2f' % self.dataclose[0])

        # Check if an order is pending... if yes, we cannot send a 2nd one
        if self.order:
            return

        if(self.datas[0].datetime.date(0) == (datetime.datetime.now().date() - datetime.timedelta(days=1))):
            if self.rsi[0] < self.rsi.params.lowerband: #Send the warning! Here
                helper.mail_sender(global_stock_name)
                print("BURA")

                



if __name__ == '__main__':

    # Bist 30
    #stock_list = ['THYAO', 'AKBNK', 'ARCLK', 'ASELS', 'BIMAS', 'DOHOL', 'EKGYO', 'EREGL'
    #, 'FROTO', 'GUBRF', 'GARAN', 'KRDMD', 'KCHOL', 'KOZAL', 'KOZAA', 'PGSUS', 'PETKM', 'SAHOL'
    #, 'SASA', 'SISE', 'TAVHL', 'TKFEN', 'TUPRS', 'TTKOM', 'TCELL', 'HALKB', 'ISCTR', 'VAKBN'
    #, 'VESTL', 'YKBNK'
    #]

    # Bist 100
    stock_list = ['THYAO', 'AKBNK', 'ARCLK', 'ASELS', 'BIMAS', 'DOHOL', 'EKGYO', 'EREGL'
    , 'FROTO', 'GUBRF', 'GARAN', 'KRDMD', 'KCHOL', 'KOZAL', 'KOZAA', 'PGSUS', 'PETKM', 'SAHOL'
    , 'SASA', 'SISE', 'TAVHL', 'TKFEN', 'TUPRS', 'TTKOM', 'TCELL', 'HALKB', 'ISCTR', 'VAKBN'
    , 'VESTL', 'YKBNK'
    , 'AEFES', 'AGHOL', ' AKCNS', 'AKSA', ' AKSEN', 'ALARK', 'ALBRK', ' ALGYO', 'ALKIM', 'ARDYZ', 'AYDEM', 'AYGAZ'
    , 'BERA',  'BRISA' # , 'BIOEN',
    , 'CANTE', 'CCOLA', 'CEMTS', 'CIMSA'
    ,  'DEVA', 'DOAS'
    , 'ECILC', 'EGEEN', 'ENJSA', 'ENKAI', 'ERBOS'      # , 'ESEN'
    , 'GLYHO', 'GOZDE', 'HEKTS', 'HLGYO', 'INDES', 'ISCTR', 'ISDMR', 'ISFIN', 'ISGYO', 'ISMEN'  #, 'IZDMC'
    , 'KARSN', 'KARTN', 'KERVT', 'KORDS' #, 'KRVGD'
    , 'LOGO'
    , 'MAVI', 'MGROS', 'MPARK'
    , 'NETAS'
    ,'ODAS', 'OTKAR', 'OYAKC', 'PARSN'
    , 'QUAGR'
    , 'SARKY', 'SELEC', 'SKBNK', 'SOKM'
    , 'TKNSA', 'TMSN', 'TOASO', 'TRGYO', 'TSKB', 'TTRAK', 'TURSG'   #, 'TRILC'
    , 'ULKER'
    , 'VERUS', 'VESBE'
    , 'YATAS'
    , 'ZOREN'#, 'ZRGYO'

    ]

    for name in stock_list:
        global_stock_name = name    # To call the stock name in the above class
        print(name)

        helper.save_stock_to_csv(name)
        # Create a cerebro entity
        cerebro = bt.Cerebro()

        # Add a strategy
        cerebro.addstrategy(TestStrategy)

        # Datas are in a subfolder of the samples. Need to find where the script is
        # because it could have been called from anywhere
        modpath = os.path.dirname(os.path.abspath(sys.argv[0]))
        datapath = os.path.join(modpath, '../datas/' + name+'.csv')

        # Create a Data Feed
        data = bt.feeds.YahooFinanceCSVData(
            dataname=datapath,
            # Do not pass values before this date
            #fromdate=datetime.datetime(2000, 1, 1),
            # Do not pass values before this date
            #todate=datetime.datetime(2000, 12, 31),
            # Do not pass values after this date
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

        #print(total)

