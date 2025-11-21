
"""
Notes:

Pass 1: Primary Resolver (Python wikipedia library)
import wikipedia

Query: Find all documents needing resolution:
todo_df = pd.Dataframe(collection.find({"wiki_resolver": {"$exists": False}}))

Process: For each company, you should create a function (e.g., fetch_wikipedia_data(...)) that encapsulates this logic.
This function must:
- Use wikipedia.search() to find the most likely page
- Use wikipedia.page() to get the page object
- Use BeautifulSoup to parse the vCard (infobox)
- Use regex to clean both the vCard (\xa0) and the main page.content (remove citations, "See Also," "References," etc/).
- Validation: Perform a check to ensure the ticker (in its dot format) is in the vcard_dict.get('Traded as', '')

Update: If succcessful, update the MongoDB document
    collection.update_one(..., {'#set': {'wiki_resolver': 'wikipedia', 'wiki_content': ..., 'wiki_vcard'}})

Note: Be polite to Wikipedia's servers, add a reasonable time.sleep() in your loop to avoid rate limiting
    
"""

## ADDED MONGO CONNECTION - swathi ###
from pymongo import MongoClient
URI = "mongodb+srv://testuser_2:admin_234@biaproject2.zxuzaya.mongodb.net/"
# Connect to MongoDB
client = MongoClient(URI)  # or your connection string

# Select your database
db = client["Project3"]

# Select your collection
Collection = db["PortfolioIntelligence"]
###################################

# Import libraries
import pandas as pd
import wikipedia
from bs4 import BeautifulSoup
import time
import re

def getFromWikipedia(Company, Ticker, URL = ''):

    if URL:
        try:
            PageTitle = URL.split('/wiki/')[-1]
            if not PageTitle:
                raise ValueError("Invalid Wikipedia URL Format")
            print(f"Provided URL Title: {PageTitle}")
        except Exception as Error:
            print(f"Error parsing given URL '{URL}': {Error}")
            return None, None, None
    else:
        print(f"No URL given, Searching for {Company} ({Ticker}) on Wikipedia")
        try:
            SearchResults = wikipedia.search(Company, results = 1)
            if not SearchResults:
                print(f"No page found for {Company}")
                return None, None, None
            PageTitle = SearchResults[0]
        except Exception as Error:
            print(f"Error in finding Wikipedia Article for {Company}: {Error}")
            return None, None, None
    
    if not PageTitle:
        print(f"No page title found for {Company}")
        return None, None, None

    try:
        Page = wikipedia.page(PageTitle, auto_suggest = False, redirect = True)
    except wikipedia.exceptions.PageError:
        print(f"Page {PageTitle} does not exist (PageError)")
        return None, None, None
    
    except wikipedia.exceptions.DisambiguationError as Error:
        print(f"Page {PageTitle} is ambiguous: {Error}")
        return None, None, None
    
    URL = Page.url

    # Utilizing Helper Functions

    VCardDictionary = ParseVCard(Page.html())
    print(VCardDictionary)

    Cleaned = CleanWikipediaContent(Page.content)

    if Ticker not in VCardDictionary.get('Traded as', ''):
        print(f"Ticker {Ticker} not found in VCard or Content for Page {URL}")
        return None, None, None

    return URL, VCardDictionary, Cleaned

# Helper Functions

def CleanWikipediaContent(Content):
    if not Content:
        return ""
    
    # Citation Marks
    Content = re.sub(r'\[\d+\]', '', Content)

    # Editorial Notes
    Content = re.sub(r'\[[a-zA-Z\s]+\]', '', Content)

    # End Sections
    EndSections = [ 'See also', 'References',
                   'External links', 'Further reading',
                   'Notes', 'Citations' ]
    for Section in EndSections:
        Content = re.split(f'\n== {Section} ==\n', Content, flags = re.IGNORECASE)[0]
    Content = re.sub(r'\n{3,}', '\n\n', Content)
    return Content.strip()

def ParseVCard(HTML):

    Soup = BeautifulSoup(HTML, 'html.parser')
    Infobox = Soup.find('table', class_ = ['inforbox', 'vcard'])
    if not Infobox:
        return {} # Infobox not found
    
    VCardDictionary = {}

    for Row in Infobox.find_all('tr'):
        Header = Row.find('th')
        Data = Row.find('td')

        if Header and Data:
            Key = Header.get_text(strip = True).replace('\xa0', ' ')
            Value = Data.get_text(separator = ' ', strip = True).replace('\xa0', ' ')

            Value = re.sub(r'\[\d+\]', '', Value)

            if Key and Value:
                VCardDictionary[Key] = Value

    return VCardDictionary


# Testing
getFromWikipedia("Microsoft", "MSFT")
getFromWikipedia("The Cheesecake Factory", "CAKE")



# Initialize Wikipedia API
wikipedia.set_user_agent('Web Mining Proj (mshi12@stevens.edu)')

DF = pd.DataFrame(Collection.find({"wiki_resolver": {"$exists": False}}))
print("Columns:", DF.columns)

for Row in DF.itertuples():
    Company = Row.company_name

    # CHANGED
    Ticker = Row.ticker # Row.ticker_dot

    print("Processing...")

    try:
        URL, VCard, Content = getFromWikipedia(Company, Ticker)

        if URL:
            doc = {
                'ticker': Ticker,
                'company_name': Company,
                'wiki_url': URL,
                'wiki_content': Content,
                'wiki_vcard': VCard,
                'wiki_resolver': 'wikipedia'
            }
            Collection.update_one(
                {'ticker': Ticker, 'etf_holding_date': Row.etf_holding_date},
                {'$set': doc} )
            print(f" No valid Wikipedia data for {Ticker}: {URL}")
        else:
            print(f" Fetched data for {Ticker}: {URL}")
    except Exception as Error:
        print(f" Unhandled exception for {Ticker}")

    time.sleep(0.25)

DoneDF = pd.DataFrame(Collection.find({"wiki_resolver": {"$exists": True}}))
S = DoneDF.wiki_url.value_counts()
S[S > 1]

## CHANGED
list(Collection.find({"ticker": "S"})) #list(Collection.find(("ticker": 'S')))

query = {
    "$and": [
        {
            "$expr": {
                "$eq": [
                    False,
                    {
                        "$regexMatch": {
                            "input": { "$replaceAll": { "input": "$wiki_content", "find": "'", "replacement": "" } },
                            "regex": {
                                "$let": {
                                    "vars": {
                                        "firstWord": {
                                            "$arrayElemAt": [ { "$split": ["$name", " "] }, 0 ]
                                        }
                                    },
                                    "in": {
                                        "$substrCP": [ "$$firstWord", 0, 6 ]
                                    }
                                }
                            },
                            "options": "i"
                        }
                    }
                ]
            }
        },
        {
            "wiki_resolver": {"$exists": True}
        }
    ]
}

# Execute Query
Mismatched = list(Collection.find(query))
print(Mismatched)


# Fix Mismatched Entries
for Doc in Mismatched:
    Update = {
        "$unset": {
            "wiki_resolver": ""
        }
    }

    ## CHANGED
    Result = Collection.update_one({'_id': Doc['_id']}, Update) #Result = Collection.update_one({'_id': doc['_id'], Update})

