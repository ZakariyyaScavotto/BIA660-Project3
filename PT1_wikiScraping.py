"""
PT1_wikiScraping.py
Helper module for Wikipedia scraping functionality.

This module provides functions to retrieve and clean Wikipedia data for companies.
It should be imported by the main pipeline, not run as a standalone script.
"""

# Import libraries
import wikipedia
from bs4 import BeautifulSoup
import re

def getFromWikipedia(Company, Ticker, URL=''):
    """
    Retrieve and validate Wikipedia data for a company.
    
    Args:
        Company (str): Company name to search for
        Ticker (str): Stock ticker symbol (in dot format, e.g., BRK.B)
        URL (str, optional): Direct Wikipedia URL to use instead of searching
    
    Returns:
        dict: Dictionary with keys 'url', 'vcard', 'content' if successful, None if failed
    """
    # Initialize Wikipedia API with user agent
    wikipedia.set_user_agent('Web Mining Proj (student@stevens.edu)')
    
    if URL:
        try:
            PageTitle = URL.split('/wiki/')[-1]
            if not PageTitle:
                raise ValueError("Invalid Wikipedia URL Format")
            print(f"Provided URL Title: {PageTitle}")
        except Exception as Error:
            print(f"Error parsing given URL '{URL}': {Error}")
            return None
    else:
        print(f"No URL given, Searching for {Company} ({Ticker}) on Wikipedia")
        try:
            SearchResults = wikipedia.search(Company, results=1)
            if not SearchResults:
                print(f"No page found for {Company}")
                return None
            PageTitle = SearchResults[0]
        except Exception as Error:
            print(f"Error in finding Wikipedia Article for {Company}: {Error}")
            return None
    
    if not PageTitle:
        print(f"No page title found for {Company}")
        return None

    try:
        Page = wikipedia.page(PageTitle, auto_suggest=False, redirect=True)
    except wikipedia.exceptions.PageError:
        print(f"Page {PageTitle} does not exist (PageError)")
        return None
    except wikipedia.exceptions.DisambiguationError as Error:
        print(f"Page {PageTitle} is ambiguous: {Error}")
        return None
    
    URL = Page.url

    # Utilizing Helper Functions
    VCardDictionary = ParseVCard(Page.html())
    print(VCardDictionary)

    Cleaned = CleanWikipediaContent(Page.content)

    # Validation: Check if ticker is in vCard
    if Ticker not in VCardDictionary.get('Traded as', ''):
        print(f"Ticker {Ticker} not found in VCard or Content for Page {URL}")
        return None

    return {
        'url': URL,
        'vcard': VCardDictionary,
        'content': Cleaned
    }

# Helper Functions

def CleanWikipediaContent(Content):
    """
    Clean Wikipedia content by removing citations, editorial notes, and end sections.
    
    Args:
        Content (str): Raw Wikipedia page content
    
    Returns:
        str: Cleaned content
    """
    if not Content:
        return ""
    
    # Citation Marks
    Content = re.sub(r'\[\d+\]', '', Content)

    # Editorial Notes
    Content = re.sub(r'\[[a-zA-Z\s]+\]', '', Content)

    # End Sections
    EndSections = ['See also', 'References',
                   'External links', 'Further reading',
                   'Notes', 'Citations']
    for Section in EndSections:
        Content = re.split(f'\n== {Section} ==\n', Content, flags=re.IGNORECASE)[0]
    Content = re.sub(r'\n{3,}', '\n\n', Content)
    return Content.strip()


def ParseVCard(HTML):
    """
    Parse the Wikipedia infobox/vCard to extract company information.
    
    Args:
        HTML (str): Raw HTML of the Wikipedia page
    
    Returns:
        dict: Dictionary of vCard fields and values
    """
    Soup = BeautifulSoup(HTML, 'html.parser')
    Infobox = Soup.find('table', class_=['infobox', 'vcard'])
    if not Infobox:
        return {}  # Infobox not found
    
    VCardDictionary = {}

    for Row in Infobox.find_all('tr'):
        Header = Row.find('th')
        Data = Row.find('td')

        if Header and Data:
            Key = Header.get_text(strip=True).replace('\xa0', ' ')
            Value = Data.get_text(separator=' ', strip=True).replace('\xa0', ' ')

            # Remove citation marks from value
            Value = re.sub(r'\[\d+\]', '', Value)

            if Key and Value:
                VCardDictionary[Key] = Value

    return VCardDictionary
