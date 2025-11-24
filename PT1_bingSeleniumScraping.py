"""
PT1_bingSeleniumScraping.py
Helper module for Bing + Selenium Wikipedia URL resolution.

This module provides functions to search Bing for Wikipedia pages when
the direct Wikipedia search API fails. It should be imported by the main
pipeline, not run as a standalone script.
"""


import time
import random
import os
from urllib.parse import quote_plus
from typing import Optional
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import WebDriverException, TimeoutException
from webdriver_manager.chrome import ChromeDriverManager
import threading
import multiprocessing
from multiprocessing import Process, Queue

# Import the Wikipedia scraper from Pass-1
from PT1_wikiScraping import getFromWikipedia

# -------------------------
# Configuration
# -------------------------
HEADLESS = False  # Do not run headless against Bing
PAGE_LOAD_TIMEOUT = 20
IMPLICIT_WAIT = 3
RETRIES = 1      # keep retries low to avoid generating bot-like traffic
POLLING_INTERVAL = 0.25  # for WebDriverWait polling
SEARCH_TIMEOUT = 120  # 2 minutes timeout for entire search operation


# -------------------------
# Utility helpers
# -------------------------
def _random_sleep(min_s=0.6, max_s=1.8):
    """Small randomized delay to mimic human pauses."""
    time.sleep(random.uniform(min_s, max_s))


def _human_like_page_warmup(driver):
    """
    Perform a short, natural sequence that mimics a human visiting the page:
      - small scrolls
      - short pauses
      - optionally move to top/bottom
    Avoids suspicious, perfectly-repeated patterns.
    """
    try:
        # small initial pause
        _random_sleep(0.5, 1.2)

        # gentle scrolls (not exact / not instantaneous)
        driver.execute_script("window.scrollBy(0, Math.min(400, document.body.scrollHeight));")
        _random_sleep(0.4, 1.0)
        driver.execute_script("window.scrollTo(0, 0);")
        _random_sleep(0.3, 0.9)
    except Exception:
        # non-fatal; warmup is best-effort
        pass


# -------------------------
# Driver creation (safe)
# -------------------------
def create_driver(headless: bool = HEADLESS,
                  page_load_timeout: int = PAGE_LOAD_TIMEOUT,
                  implicit_wait: int = IMPLICIT_WAIT,
                  profile_dir: Optional[str] = None,
                  prefer_local_driver: bool = False):
    """
    Create a conservative, stable Chrome WebDriver instance.

    Args:
        headless: whether to run headless (not recommended for Bing).
        page_load_timeout: max time for page loads.
        implicit_wait: Selenium implicit wait.
        profile_dir: path to a persistent Chrome profile dir (recommended).
                     If None, a temporary profile is used by Chrome (Selenium default).
        prefer_local_driver: if True, tries to use a locally installed chromedriver
                             binary instead of webdriver_manager. (Optional)

    Returns:
        selenium.webdriver.Chrome
    """
    chrome_options = Options()

    # Headed/browser behavior
    if headless:
        # NOTE: headless is discouraged for Bing and many sites; only enable if necessary.
        chrome_options.add_argument("--headless=new")
        chrome_options.add_argument("--window-size=1280,900")
    else:
        # start maximized provides consistent geometry
        chrome_options.add_argument("--start-maximized")

    # Basic innocuous flags
    chrome_options.add_argument("--disable-notifications")
    chrome_options.add_argument("--disable-popup-blocking")
    chrome_options.add_argument("--no-default-browser-check")
    chrome_options.add_argument("--ignore-certificate-errors")
    chrome_options.add_argument("--disable-extensions")  # keep extension background noise low

    # Rotate among a short list of realistic user agents to reduce repeated identical UA strings
    USER_AGENTS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36",
    ]
    chrome_options.add_argument(f"--user-agent={random.choice(USER_AGENTS)}")

    # Use a persistent profile if provided — this makes behaviour look more "real".
    if profile_dir:
        os.makedirs(profile_dir, exist_ok=True)
        chrome_options.add_argument(f"--user-data-dir={profile_dir}")

    # Use webdriver-manager to obtain a compatible chromedriver for the local Chrome version
    # (webdriver_manager will pick a version that matches installed Chrome)
    # Get the driver path
    driver_path = ChromeDriverManager().install()
    
    # Create driver without Service object to avoid version conflicts
    # This approach works across Selenium 3.x and 4.x
    try:
        # Try Selenium 4.x style first
        from selenium.webdriver.chrome.service import Service as ChromeService
        service = ChromeService(executable_path=driver_path)
        driver = webdriver.Chrome(service=service, options=chrome_options)
    except (ImportError, TypeError):
        # Fallback to Selenium 3.x style
        driver = webdriver.Chrome(executable_path=driver_path, options=chrome_options)

    # Timeouts / waits
    driver.set_page_load_timeout(page_load_timeout)
    driver.implicitly_wait(implicit_wait)

    return driver


# -------------------------
# Bing search helpers
# -------------------------
def bing_url(query: str) -> str:
    """Generate Bing search URL for a query."""
    return f"https://www.bing.com/search?q={quote_plus(query)}"


def extract_wikipedia_url(driver, debug=False):
    """
    Extract the first matching Wikipedia URL from the currently loaded Bing results page.

    Strategy:
      - Look for standard result anchors (li.b_algo h2 a)
      - If an anchor href is a bing redirect (contains /ck/a), navigate to that href (driver.get)
        which will perform the redirect server-side and land on the final page.
      - Avoid ctrl-clicks or opening new tabs; navigating to the redirect target in the same tab
        is consistent and less noisy.
    """
    selectors = ["li.b_algo h2 a"]
    for selector in selectors:
        try:
            anchors = driver.find_elements(By.CSS_SELECTOR, selector)
            if debug:
                print(f"DEBUG: Found {len(anchors)} anchors for selector {selector}")

            for idx, a in enumerate(anchors):
                try:
                    href = a.get_attribute("href")
                except Exception as e:
                    if debug:
                        print(f"DEBUG: Failed to get href for anchor {idx}: {e}")
                    continue

                if not href:
                    continue

                if debug and idx < 4:
                    print(f"DEBUG: candidate href[{idx}] = {href[:140]}")

                # If it looks like a direct Wikipedia link, return it
                if "en.wikipedia.org/wiki/" in href:
                    clean_url = href.split("#")[0].split("?")[0]
                    if debug:
                        print(f"DEBUG: Direct Wikipedia URL found: {clean_url}")
                    return clean_url

                # If it's a bing redirect (contains '/ck/a' or '/r.php' style redirects),
                # navigate to it and let the browser follow redirects.
                if "bing.com/ck/a" in href or "/r.php" in href or "go.microsoft.com" in href:
                    if debug:
                        print(f"DEBUG: Following Bing redirect href[{idx}] via driver.get() to resolve target")
                    try:
                        current = driver.current_url
                        driver.get(href)  # follow redirect server-side
                        # small wait for redirect to complete
                        time.sleep(random.uniform(0.9, 1.6))
                        actual_url = driver.current_url
                        if debug:
                            print(f"DEBUG: Resolved redirect to {actual_url}")
                        # navigate back to results so we don't lose context (best-effort)
                        try:
                            driver.back()
                            _random_sleep(0.4, 1.0)
                        except Exception:
                            pass

                        if actual_url and "en.wikipedia.org/wiki/" in actual_url:
                            clean_url = actual_url.split("#")[0].split("?")[0]
                            if debug:
                                print(f"DEBUG: ✓ Resolved Wikipedia URL: {clean_url}")
                            return clean_url
                    except Exception as e:
                        if debug:
                            print(f"DEBUG: Error while resolving redirect: {e}")
                        # try continuing with other anchors
                        try:
                            # attempt to restore original results page if possible
                            if driver.current_url != current:
                                driver.get(current)
                        except Exception:
                            pass
                        continue

                # Otherwise continue scanning anchors
            # end anchors loop
        except Exception as e:
            if debug:
                print(f"DEBUG: selector {selector} failed: {e}")
            continue

    if debug:
        try:
            with open("bing_debug.html", "w", encoding="utf-8") as f:
                f.write(driver.page_source)
            print("DEBUG: saved page source to bing_debug.html")
        except Exception:
            pass

    return None


def search_bing_for_wiki(company: str, ticker: str, driver, debug=False):
    """
    Search Bing for the company's Wikipedia page and return the best match URL (or None).

    This function is deliberately conservative:
      - warms up the session
      - performs waits for results to render
      - uses polite random delays
    """
    query = f"{company} site:wikipedia.org"
    url = bing_url(query)

    try:
        if debug:
            print(f"DEBUG: Navigating to Bing search URL: {url}")
        driver.get(url)
    except Exception as e:
        if debug:
            print(f"DEBUG: driver.get failed: {e}")
        return None

    # Gentle human-like warmup
    _human_like_page_warmup(driver)

    # Wait for search results container or a 'no results' indicator
    try:
        wait = WebDriverWait(driver, 15, poll_frequency=POLLING_INTERVAL)
        wait.until(
            lambda d: len(d.find_elements(By.CSS_SELECTOR, "li.b_algo")) > 0
                      or len(d.find_elements(By.CSS_SELECTOR, ".b_no")) > 0
                      or len(d.find_elements(By.CSS_SELECTOR, "#b_results")) > 0
        )
    except TimeoutException:
        if debug:
            print("DEBUG: Timeout waiting for results container")
        # still attempt extraction; maybe client-side rendering finished late
        _random_sleep(0.4, 1.0)

    # small randomized pause before parsing
    _random_sleep(0.8, 1.6)

    if debug:
        try:
            print(f"DEBUG: Page title: {driver.title}")
            print(f"DEBUG: Current URL: {driver.current_url}")
        except Exception:
            pass

    return extract_wikipedia_url(driver, debug=debug)


# -------------------------
# Top-level function used by pipeline
# -------------------------
def _search_with_timeout_worker(company, ticker, retries, profile_dir, result_queue):
    """Worker function that runs in a separate process with timeout"""
    driver = None
    try:
        # Create driver
        driver = create_driver(headless=HEADLESS, page_load_timeout=PAGE_LOAD_TIMEOUT,
                               implicit_wait=IMPLICIT_WAIT, profile_dir=profile_dir)

        wikipedia_url = None
        for attempt in range(1, retries + 1):
            wikipedia_url = search_bing_for_wiki(company, ticker, driver, debug=False)
            if wikipedia_url:
                break
            # polite backoff
            if attempt < retries:
                delay = random.uniform(3.0, 6.0)
                time.sleep(delay)

        if wikipedia_url:
            # Validate & fetch content
            wiki_data = getFromWikipedia(company, ticker, URL=wikipedia_url)
            result_queue.put(('success', wikipedia_url, wiki_data))
        else:
            result_queue.put(('no_url', None, None))

    except Exception as err:
        result_queue.put(('error', None, str(err)))
    finally:
        if driver:
            try:
                driver.quit()
            except:
                pass


def getFromBingSelenium(company: str, ticker: str, retries: int = RETRIES, profile_dir: Optional[str] = None):
    """
    Main function to retrieve Wikipedia data via Bing + Selenium with timeout.

    Returns the same data structure as getFromWikipedia (dict with keys 'url','vcard','content') or None.
    """
    print(f"Searching Bing for {company} ({ticker})")
    print("  → Creating Chrome driver...")

    # Create a queue for results
    result_queue = Queue()
    
    # Create and start the worker process
    worker = Process(target=_search_with_timeout_worker, 
                    args=(company, ticker, retries, profile_dir, result_queue))
    worker.start()
    
    # Wait for the process with timeout
    worker.join(timeout=SEARCH_TIMEOUT)
    
    # Check if process is still alive (timed out)
    if worker.is_alive():
        print(f"  ✗ Timeout: Search exceeded 2 minutes for {ticker} - killing process")
        worker.terminate()
        worker.join(timeout=5)  # Wait up to 5 seconds for graceful termination
        if worker.is_alive():
            worker.kill()  # Force kill if still alive
        return None
    
    # Get result from queue
    if not result_queue.empty():
        status, url, data = result_queue.get()
        
        if status == 'success':
            if data:
                print(f"  ✓ Validation success for {ticker}")
                return data
            else:
                print(f"  ✗ Validation failed for {ticker}")
                return None
        elif status == 'no_url':
            print(f"  ✗ No Wikipedia URL found for {ticker} via Bing")
            return None
        elif status == 'error':
            print(f"  ✗ Error in Bing search for {ticker}: {data}")
            return None
    
    print(f"  ✗ No result returned for {ticker}")
    return None


# -------------------------
# Testing function
# -------------------------
def test_bing_selenium():
    print("=" * 70)
    print("TESTING BING + SELENIUM SCRAPING")
    print("=" * 70)

    test_cases = [
        {"company": "INSULET Corp", "ticker": "PODD"},
    ]

    results = []
    for i, test in enumerate(test_cases, 1):
        company = test["company"]
        ticker = test["ticker"]

        print(f"\n[Test {i}/{len(test_cases)}] Testing: {company} ({ticker})")
        print("-" * 70)

        try:
            # Optionally pass a profile_dir path if you want a persistent profile:
            # e.g. profile_dir=r"C:\Users\<you>\selenium_profile"
            result = getFromBingSelenium(company, ticker, retries=RETRIES, profile_dir=None)

            if result:
                print("✓ SUCCESS")
                print(f"  URL: {result['url'][:120]}...")
                print(f"  Content length: {len(result['content'])} chars")
                print(f"  VCard fields: {len(result['vcard'])} fields")
                results.append({"ticker": ticker, "status": "PASS", "error": None})
            else:
                print("✗ FAILED - No data returned")
                results.append({"ticker": ticker, "status": "FAIL", "error": "No data returned"})
        except Exception as e:
            print(f"✗ ERROR - {e}")
            results.append({"ticker": ticker, "status": "ERROR", "error": str(e)})

    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)
    passed = sum(1 for r in results if r["status"] == "PASS")
    failed = sum(1 for r in results if r["status"] == "FAIL")
    errors = sum(1 for r in results if r["status"] == "ERROR")
    print(f"Total tests: {len(results)}")
    print(f"Passed:      {passed}")
    print(f"Failed:      {failed}")
    print(f"Errors:      {errors}")

    if passed == len(results):
        print("\n✓ ALL TESTS PASSED!")
    else:
        print("\n✗ Some tests failed. Check errors above.")
        for r in results:
            if r["status"] != "PASS":
                print(f"  - {r['ticker']}: {r['error']}")
    print("=" * 70)
    return results


if __name__ == "__main__":
    print("Running Bing + Selenium scraper tests...\n")
    test_bing_selenium()