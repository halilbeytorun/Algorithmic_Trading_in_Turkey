# Will be having helper functions like saving data
import yfinance as yf
import datetime
import pandas as pd
from string import Template
import smtplib


#start = datetime.datetime(2021,1,1)
#end = datetime.datetime(2021,9,25)



def save_stock_to_csv(stock_name: str):
    '''
    Saves the stock given to a csv file
    '''

    offset = datetime.timedelta(days=50)    # To save the last days= into csv
    end = datetime.datetime.now().date()

    end = datetime.datetime(end.year, end.month, end.day)
    start = end - offset

    stock_names_dict = {'THYAO': 'THYAO.IS', 'AKBNK': 'AKBNK.IS', 'ARCLK':'ARCLK.IS'
    , 'ASELS': 'ASELS.IS', 'BIMAS': 'BIMAS.IS', 'DOHOL' :'DOHOL.IS', 'EKGYO':'EKGYO.IS'
    , 
    }    # Add stock names when you add them from looking to their yahoo rep

    #stock = yf.download(stock_names_dict[stock_name], start, end, progress=False)
    stock = yf.download(stock_name + '.IS', start, end, progress=False)
    stock.to_csv("./data/" + stock_name + '.csv')

def mail_sender(stock_name: str):
    '''
    Sends warning mail to me
    '''
    FROM = 'botmail'
    TO = ['yourmail']
    SUBJECT = 'Buy stockkkk'
    TEXT = 'The stock: -' + stock_name + '- is below the desired RSI point. Go in bro'

    # Prepare actual message
    message = """From: %s\nTo: %s\nSubject: %s\n\n%s
    """ % (FROM, ", ".join(TO), SUBJECT, TEXT)


    s = smtplib.SMTP_SSL('smtp.gmail.com', 465)
    s.ehlo()
    mail_password = "123"
    s.login(FROM, mail_password)

    s.sendmail(FROM, TO, message)
    s.close



