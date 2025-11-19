# Imports

import yfinance as yf

def getFromYahooFinance(ticker):
    print(f"Getting data from Yahoo Finance for {ticker}...")

for i, Row in DF.copy().iterrows():
    YFTic = yf.ticker(Row.ticker)
    if not 'longBusinessSummary' in YFTic.info:
        YFTic = yf.ticker(Row.ticker.replace('.','-'))

    try:
        VCardColumns = ['address1', 'city', 'state', 'zip', 'country', 'phone', 'website', 'industry', 'industryKey', 'industryDisp']