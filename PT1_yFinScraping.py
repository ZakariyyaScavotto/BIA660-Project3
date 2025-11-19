# Imports

import pandas as pd
import yfinance as yf

def getFromYahooFinance(ticker):
    print(f"Getting data from Yahoo Finance for {ticker}...")

for i, Row in DF.copy().iterrows():
    YFTic = yf.ticker(Row.ticker)
    if not 'longBusinessSummary' in YFTic.info:
        YFTic = yf.ticker(Row.ticker.replace('.','-'))

    try:
        VCardColumns = ['address1', 'city', 'state', 'zip', 'country', 'phone', 'website', 'industry', 'industryKey', 'industryDisp']
        VCardDictionary = {K:v for K,v in YFTic.info.items() if k in VCardColumns}
        Content = YFTic.info['longBusinessSummary']
        print(Row.ticker, Content)
        Collection.update_one(
            {'ticker': Row.ticker,
             'etf_holding_date': Row.etf_holding_date},
             {'#set':
              {
                  'wiki_resolver': 'yfinance',
                  'wiki_content': Content,
                  'wiki_vcard': VCardDictionary,
              }
            }
        )
    except:
        0