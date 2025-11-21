
"""
PT1_bingSeleniumScraping.py
Pass 2: Bing + Selenium resolver for unresolved MongoDB documents.

This script:
    • Searches Bing for a Wikipedia page for each unresolved company
    • Extracts the Wikipedia URL from Bing results
    • Sends that URL to getFromWikipedia() (from Pass-1)
    • If validation succeeds, updates the MongoDB document with wiki_* fields
"""

import os
import time
import logging
import traceback
from urllib.parse import quote_plus

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import WebDriverException, TimeoutException
from webdriver_manager.chrome import ChromeDriverManager

from pymongo import MongoClient
from dotenv import load_dotenv

# Import your updated Pass-1 resolver
from PT1_wikiScraping import getFromWikipedia

# Load environment variables (optional)
load_dotenv()

# -------------------------
# Configuration
# -------------------------
MONGO_URI = os.getenv("MONGO_URI", "mongodb+srv://testuser_2:admin_234@biaproject2.zxuzaya.mongodb.net/")
DB_NAME = os.getenv("MONGO_DB", "Project3")
COLLECTION_NAME = os.getenv("MONGO_COLLECTION", "PortfolioIntelligence")

HEADLESS = True
PAGE_LOAD_TIMEOUT = 12
IMPLICIT_WAIT = 2
SLEEP_BETWEEN = 1.5
RETRIES = 2
BATCH_SIZE = 150

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("bing_resolver")


# -------------------------
# MongoDB helper
# -------------------------
def get_collection():
    client = MongoClient(MONGO_URI)
    return client[DB_NAME][COLLECTION_NAME]


# -------------------------
# Selenium helpers
# -------------------------
def create_driver():
    """Create Chrome WebDriver."""
    options = Options()
    if HEADLESS:
        options.add_argument("--headless=new")

    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--user-agent=Mozilla/5.0")

    prefs = {"profile.managed_default_content_settings.images": 2}
    options.add_experimental_option("prefs", prefs)

    driver = webdriver.Chrome(ChromeDriverManager().install(), options=options)
    driver.set_page_load_timeout(PAGE_LOAD_TIMEOUT)
    driver.implicitly_wait(IMPLICIT_WAIT)
    return driver


def extract_wikipedia_url(driver):
    """Return the first Wikipedia link on the Bing results page."""
    try:
        anchors = driver.find_elements(By.CSS_SELECTOR, "li.b_algo h2 a")
    except Exception:
        anchors = []

    for a in anchors:
        try:
            href = a.get_attribute("href")
            if href and "en.wikipedia.org/wiki/" in href:
                return href.split("#")[0].split("?")[0]
        except:
            pass
    return None


def bing_url(query: str) -> str:
    return f"https://www.bing.com/search?q={quote_plus(query)}"


def search_bing_for_wiki(company: str, ticker: str, driver) -> str | None:
    """Return best Wikipedia URL extracted from Bing search results."""
    query = f"{ticker} {company} Company Wikipedia"
    url = bing_url(query)

    try:
        driver.get(url)
    except Exception:
        return None

    time.sleep(1.0)
    return extract_wikipedia_url(driver)


# -------------------------
# Main resolver pass
# -------------------------
def bing_resolver():
    coll = get_collection()
    logger.info("Running Bing resolver against %s.%s", DB_NAME, COLLECTION_NAME)

    # Find unresolved docs
    docs = list(coll.find({"wiki_resolver": {"$exists": False}}).limit(BATCH_SIZE))
    logger.info("Found %d unresolved docs", len(docs))

    if not docs:
        return

    driver = create_driver()
    processed = 0

    for doc in docs:
        processed += 1
        company = doc.get("company_name")
        ticker = doc.get("ticker")

        if not company or not ticker:
            logger.warning("Skipping document missing company/ticker: %s", doc["_id"])
            continue

        logger.info("[%d/%d] Searching for %s (%s)", processed, len(docs), company, ticker)

        wikipedia_url = None
        for attempt in range(RETRIES):
            wikipedia_url = search_bing_for_wiki(company, ticker, driver)
            if wikipedia_url:
                break
            time.sleep(0.5)

        if not wikipedia_url:
            logger.info("No Wikipedia URL found for %s", ticker)
            continue

        logger.info("Candidate Wikipedia page found: %s", wikipedia_url)

        # Validate using your Pass-1 scraper
        try:
            resolved_url, vcard, cleaned = getFromWikipedia(company, ticker, URL=wikipedia_url)
        except Exception as err:
            logger.error("Error in Pass-1 validation: %s", err)
            resolved_url = None

        if resolved_url and vcard and cleaned:
            logger.info("Validation success — updating MongoDB for %s", ticker)

            update_doc = {
                "wiki_resolver": "bing",
                "wiki_url": resolved_url,
                "wiki_vcard": vcard,
                "wiki_content": cleaned,
                "wiki_resolver_meta": {
                    "timestamp": time.time(),
                    "method": "bing_selenium"
                }
            }

            coll.update_one({"_id": doc["_id"]}, {"$set": update_doc})
        else:
            logger.info("Validation failed — leaving %s unresolved", ticker)

        time.sleep(SLEEP_BETWEEN)

    driver.quit()
    logger.info("Bing resolver finished. Processed %d docs.", processed)


# -------------------------
# Run as script
# -------------------------
if __name__ == "__main__":
    bing_resolver()






















































