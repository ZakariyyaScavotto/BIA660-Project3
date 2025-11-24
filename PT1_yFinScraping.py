"""
PT1_yFinScraping.py
Helper module for Yahoo Finance data retrieval.

This module provides functions to retrieve company business summaries and
information from Yahoo Finance as a fallback when Wikipedia data is unavailable.
It should be imported by the main pipeline, not run as a standalone script.
"""

# Imports
import yfinance as yf


def getFromYahooFinance(ticker):
    """
    Retrieve company data from Yahoo Finance.
    
    Args:
        ticker (str): Stock ticker symbol (supports both dot and dash formats)
    
    Returns:
        dict: Dictionary with keys 'url', 'vcard', 'content' if successful, None if failed
    """
    print(f"Getting data from Yahoo Finance for {ticker}...")
    
    # Try original ticker format first
    yf_ticker = yf.Ticker(ticker)
    
    # If longBusinessSummary not found, try dash format (e.g., BRK.B -> BRK-B)
    if 'longBusinessSummary' not in yf_ticker.info:
        ticker_dash = ticker.replace('.', '-')
        print(f"Trying dash format: {ticker_dash}")
        yf_ticker = yf.Ticker(ticker_dash)
    
    try:
        # Extract vCard-like information
        vcard_columns = ['address1', 'city', 'state', 'zip', 'country', 
                        'phone', 'website', 'industry', 'industryKey', 
                        'industryDisp', 'sector']
        
        # Build vCard dictionary (fixed: was using undefined 'k' instead of 'K')
        vcard_dictionary = {K: v for K, v in yf_ticker.info.items() if K in vcard_columns}
        
        # Get business summary content
        content = yf_ticker.info.get('longBusinessSummary', '')
        
        if not content:
            print(f"No business summary found for {ticker}")
            return None
        
        print(f"Successfully retrieved Yahoo Finance data for {ticker}")
        
        return {
            'url': f"https://finance.yahoo.com/quote/{ticker}",
            'vcard': vcard_dictionary,
            'content': content
        }
        
    except Exception as e:
        print(f"Error retrieving Yahoo Finance data for {ticker}: {e}")
        return None
    