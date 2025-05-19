import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import time
import pandas as pd
import re
import json
from collections import defaultdict
import datetime
import os

# Define available towns and their coordinates
TOWNS = {
    "Milton": {
        "center": "43.523208,-79.943640",
        "lat_max": "43.71062",
        "long_max": "-79.62195",
        "lat_min": "43.33521",
        "long_min": "-80.26533",
        "geo_id": "g30_dpxpsf37"
    },
    "Oakville": {
        "center": "43.447781,-79.713555",
        "lat_max": "43.54168",
        "long_max": "-79.42568",
        "lat_min": "43.35374",
        "long_min": "-80.00143",
        "geo_id": "g30_dpxr1yrj"
    },
    "Burlington": {
        "center": "43.381425,-79.839745",
        "lat_max": "43.56928",
        "long_max": "-79.26399",
        "lat_min": "43.19299",
        "long_min": "-80.41550",
        "geo_id": "g30_dpxnz15m"
    },
    "Mississauga": {
        "center": "43.606263,-79.666605",
        "lat_max": "43.85880",
        "long_max": "-78.74719",
        "lat_min": "43.35266",
        "long_min": "-80.58602",
        "geo_id": "g30_dpxrgruz"
    },
    "Brampton": {
        "center": "43.725101,-79.759570",
        "lat_max": "43.97714",
        "long_max": "-78.84015",
        "lat_min": "43.47200",
        "long_min": "-80.67899",
        "geo_id": "g30_dpz29nnj"
    },
    "Halton Hills": {
        "center": "43.465905,-79.924625",
        "lat_max": "43.59260",
        "long_max": "-79.46492",
        "lat_min": "43.33894",
        "long_min": "-80.38433",
        "geo_id": "g30_dpz0hvkr"
    },
    "Hamilton": {
        "center": "43.261153,-79.935270",
        "lat_max": "43.51514",
        "long_max": "-79.01585",
        "lat_min": "43.00610",
        "long_min": "-80.85469",
        "geo_id": "g30_dpxnh9by"
    },
    "Guelph": {
        "center": "43.534350,-80.240165",
        "lat_max": "43.66091",
        "long_max": "-79.78046",
        "lat_min": "43.40753",
        "long_min": "-80.69987",
        "geo_id": "g30_dpwzwhvk"
    },
    "Kitchener": {
        "center": "43.430423,-80.476415",
        "lat_max": "43.55720",
        "long_max": "-80.01671",
        "lat_min": "43.30338",
        "long_min": "-80.93612",
        "geo_id": "g30_dpwz0be2"
    },
    "Cambridge": {
        "center": "43.402370,-80.332605",
        "lat_max": "43.52920",
        "long_max": "-79.87290",
        "lat_min": "43.27527",
        "long_min": "-80.79231",
        "geo_id": "g30_dpwyuhfd"
    }
}

def select_towns():
    """Prompt user to select towns to search"""
    print("\nAvailable towns:")
    for i, town in enumerate(TOWNS.keys(), 1):
        print(f"{i}. {town}")
    print("Enter numbers separated by commas (e.g., 1,2,3) or press Enter for all towns")
    
    selection = input("Select towns to search: ").strip()
    if not selection:
        return list(TOWNS.keys())
    
    try:
        indices = [int(x.strip()) - 1 for x in selection.split(",")]
        selected_towns = [list(TOWNS.keys())[i] for i in indices if 0 <= i < len(TOWNS)]
        return selected_towns if selected_towns else list(TOWNS.keys())
    except (ValueError, IndexError):
        print("Invalid selection. Searching all towns.")
        return list(TOWNS.keys())

def get_pages_per_town():
    """Prompt user for number of pages to scrape per town"""
    while True:
        try:
            pages = input("\nEnter number of pages to scrape per town (1-50): ").strip()
            if not pages:
                print("Using default of 3 pages per town")
                return 3
            
            pages = int(pages)
            if 1 <= pages <= 50:
                return pages
            else:
                print("Please enter a number between 1 and 50")
        except ValueError:
            print("Please enter a valid number")

def get_town_url(town_name):
    """Generate URL for a specific town (first page)"""
    town_data = TOWNS[town_name]
    base_url = (
        f"https://www.realtor.ca/map#ZoomLevel=11"
        f"&Center={town_data['center']}"
        f"&LatitudeMax={town_data['lat_max']}"
        f"&LongitudeMax={town_data['long_max']}"
        f"&LatitudeMin={town_data['lat_min']}"
        f"&LongitudeMin={town_data['long_min']}"
        f"&Sort=6-D"
        f"&GeoIds={town_data['geo_id']}"
        f"&GeoName={town_name}%2C%20ON"
        f"&PropertyTypeGroupID=1"
        f"&TransactionTypeId=2"
        f"&PropertySearchTypeId=0"
        f"&Currency=CAD"
    )
    return base_url

def wait_for_listings(driver, timeout=8, max_retries=2):
    """Wait for listings to load on the page with retries"""
    for retry in range(max_retries):
        try:
            WebDriverWait(driver, timeout).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div.smallListingCardBodyWrap"))
            )
            return True
        except TimeoutException:
            if retry < max_retries - 1:
                print(f"⚠️ Timeout waiting for listings, retrying ({retry+1}/{max_retries})...")
                # Refresh the page on second retry
                if retry == 1:
                    try:
                        driver.refresh()
                        # Wait for page to be ready after refresh with reduced timeout
                        WebDriverWait(driver, timeout).until(
                            lambda d: d.execute_script("return document.readyState") == "complete"
                        )
                    except:
                        pass
                time.sleep(0.5)  # Reduced wait time
            else:
                return False
    return False

def wait_for_page_ready(driver, timeout=10, additional_wait=0.2):
    """Wait for the page to be fully loaded and ready"""
    try:
        # Wait for the document to be ready
        WebDriverWait(driver, timeout).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )
        
        # Reduced additional wait time
        time.sleep(additional_wait)
        return True
    except TimeoutException:
        return False

def navigate_to_next_page(driver, timeout=8, max_retries=2):
    """Click the next page button and wait for the page to load with retry mechanism"""
    for retry in range(max_retries):
        try:
            # Wait for page to be ready
            wait_for_page_ready(driver)
            
            # Find the next button - reduced initial wait time
            next_button = WebDriverWait(driver, timeout).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "a.lnkNextResultsPage"))
            )
            
            # Check if the button is disabled
            if next_button.get_attribute("disabled") == "disabled":
                print("⚠️ Next page button is disabled - reached the last page")
                return False
            
            # Scroll to make the button visible and click immediately
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'}); arguments[0].click();", next_button)
            print("🔄 Clicked next page button")
            
            # Reduced wait time for page ready
            wait_for_page_ready(driver, timeout=5)
            
            # Wait for listings to appear with reduced timeout
            if wait_for_listings(driver, timeout=5, max_retries=1):
                print("✅ Next page loaded successfully")
                return True
            else:
                print(f"⚠️ Next page may not have loaded properly (attempt {retry+1}/{max_retries})")
                if retry < max_retries - 1:
                    time.sleep(0.5)  # Reduced wait time
                    continue
                return False
                
        except (TimeoutException, NoSuchElementException) as e:
            print(f"❌ Error navigating to next page (attempt {retry+1}/{max_retries}): {str(e)[:100]}...")
            if retry < max_retries - 1:
                time.sleep(0.5)  # Reduced wait time
                continue
            return False
    
    return False

def get_listing_urls(driver, max_retries=2):
    """Get all listing URLs from the current page with retry mechanism"""
    urls = []
    
    for retry in range(max_retries):
        try:
            # Make sure page is fully loaded with reduced timeout
            wait_for_page_ready(driver, timeout=5)
            
            # Wait for listings to be visible with reduced timeout
            WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "a.listingDetailsLink"))
            )
            
            # Try a more reliable approach using explicit waiting for each element
            cards = WebDriverWait(driver, 5).until(
                EC.presence_of_all_elements_located((By.CSS_SELECTOR, "div.cardCon"))
            )
            
            for card in cards[:12]:  # Limit to first 12 listings
                try:
                    # Find link within this specific card to avoid stale element issues
                    link = WebDriverWait(card, 3).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, "a.listingDetailsLink"))
                    )
                    url = link.get_attribute("href")
                    if url and url not in urls:  # Avoid duplicates
                        urls.append(url)
                except Exception as e:
                    # Continue with next card if one fails
                    print(f"⚠️ Error getting URL from card: {str(e)[:100]}...")
                    continue
            
            if urls:
                break  # Exit retry loop if we got some URLs
                
        except Exception as e:
            print(f"⚠️ Error getting listing URLs (attempt {retry+1}/{max_retries}): {str(e)[:100]}...")
            if retry < max_retries - 1:
                time.sleep(0.5)  # Reduced wait time
                # Refresh the page if we're having trouble
                if retry == 1:  # Try refreshing on second attempt
                    try:
                        driver.refresh()
                        wait_for_page_ready(driver, timeout=5)
                    except:
                        pass
    
    return urls

def return_to_map_view(driver, map_url, max_retries=3):
    """Safely return to map view with retries"""
    for retry in range(max_retries):
        try:
            print("🔄 Returning to map view")
            driver.get(map_url)
            
            # Wait for page to be ready
            if wait_for_page_ready(driver) and wait_for_listings(driver, 10):
                return True
            
            if retry < max_retries - 1:
                print(f"⚠️ Map view not loaded properly, retrying ({retry+1}/{max_retries})...")
                time.sleep(1)
            else:
                print("⚠️ Failed to return to map view after multiple attempts")
                return False
                
        except Exception as e:
            print(f"❌ Error returning to map view (attempt {retry+1}/{max_retries}): {str(e)[:100]}...")
            if retry < max_retries - 1:
                time.sleep(1)
            else:
                return False
    
    return False

def switch_to_town(driver, town, max_retries=2):
    """Safely switch to a new town with retry mechanism"""
    for retry in range(max_retries):
        try:
            print(f"\n🔄 Switching to {town}...")
            town_url = get_town_url(town)
            print(f"Navigating to: {town_url}")
            
            # Navigate to the town's first page
            driver.get(town_url)
            
            # Wait for page to be ready with reduced timeout
            if not wait_for_page_ready(driver, timeout=10):
                print(f"⚠️ Page not ready for {town} (attempt {retry+1}/{max_retries})")
                if retry < max_retries - 1:
                    time.sleep(1)  # Reduced wait time
                    continue
            
            # Wait for listings to appear with reduced timeout
            if not wait_for_listings(driver, timeout=10, max_retries=2):
                print(f"⚠️ No listings found for {town} (attempt {retry+1}/{max_retries})")
                if retry < max_retries - 1:
                    time.sleep(1)  # Reduced wait time
                    continue
                
            # VERIFICATION: Check if we're actually on the correct town page
            try:
                time.sleep(0.5)  # Reduced wait time
                page_source = driver.page_source
                
                # Force a hard refresh to ensure we're not looking at cached content
                driver.execute_script("location.reload(true);")
                wait_for_page_ready(driver, timeout=10)
                wait_for_listings(driver, timeout=10)
                
                # Multiple verification attempts
                found_correct_town = False
                
                # Check 1: Look for town name in URL
                current_url = driver.current_url
                if town.lower() in current_url.lower():
                    print(f"✅ Verified {town} in URL: {current_url[:50]}...")
                    found_correct_town = True
                
                # Check 2: Look for town name in breadcrumbs or filter sections
                try:
                    # Wait for breadcrumbs to load with reduced timeout
                    WebDriverWait(driver, 5).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, ".breadcrumbSection, .contextualLinks, .mainFilter"))
                    )
                    page_text = driver.find_element(By.CSS_SELECTOR, "body").text
                    if town in page_text:
                        print(f"✅ Verified {town} found in page text")
                        found_correct_town = True
                except:
                    pass
                
                # If verification failed, try once more with a different approach
                if not found_correct_town:
                    print(f"⚠️ Could not verify we're on {town} page. Trying alternate verification...")
                    
                    # Try clicking on filter section which might show town name
                    try:
                        filter_elements = driver.find_elements(By.CSS_SELECTOR, ".mainFilter, .filterButton")
                        if filter_elements:
                            filter_elements[0].click()
                            time.sleep(0.5)  # Reduced wait time
                            page_text = driver.find_element(By.CSS_SELECTOR, "body").text
                            if town in page_text:
                                print(f"✅ Verified {town} in filter text after clicking")
                                found_correct_town = True
                    except:
                        pass
                
                # Final check - if still not verified, check if our GeoId is in URL
                if not found_correct_town:
                    geo_id = TOWNS[town]["geo_id"]
                    if geo_id in driver.current_url or geo_id in driver.page_source:
                        print(f"✅ Verified {town} by GeoId: {geo_id}")
                        found_correct_town = True
                
                if not found_correct_town:
                    print(f"⚠️ Failed to verify we're on {town} page (attempt {retry+1}/{max_retries})")
                    if retry < max_retries - 1:
                        # Try to clear cache and cookies before retrying
                        try:
                            driver.delete_all_cookies()
                            driver.execute_script("window.localStorage.clear();")
                            driver.execute_script("window.sessionStorage.clear();")
                        except:
                            pass
                        time.sleep(1)  # Reduced wait time
                        continue
                    return False
            except Exception as e:
                print(f"⚠️ Error during town verification: {str(e)[:100]}...")
                if retry < max_retries - 1:
                    time.sleep(1)  # Reduced wait time
                    continue
                return False
            
            print(f"✅ Successfully switched to {town}")
            return True
            
        except Exception as e:
            print(f"❌ Error switching to {town} (attempt {retry+1}/{max_retries}): {str(e)[:100]}...")
            if retry < max_retries - 1:
                time.sleep(1)  # Reduced wait time
                continue
            return False
    
    return False

# Create scrapes directory if it doesn't exist
scrapes_dir = "scrapes"
if not os.path.exists(scrapes_dir):
    os.makedirs(scrapes_dir)

# Set up browser function to allow for restarts as needed
def setup_browser():
    """Create and configure a new browser instance"""
    print("🔄 Setting up browser...")
    driver = uc.Chrome()
    driver.maximize_window()
    return driver

# Initialize driver
driver = setup_browser()

# Variable to track consecutive listing errors
consecutive_listing_errors = 0
max_consecutive_errors = 5  # Restart browser after this many consecutive errors

# Go to Realtor.ca
print("Opening Realtor.ca...")
driver.get("https://www.realtor.ca")

# Get town selection from user
selected_towns = select_towns()
print(f"\nSearching in: {', '.join(selected_towns)}")

# Get number of pages to scrape per town
max_pages = get_pages_per_town()
print(f"Will scrape {max_pages} pages per town")

# Remove manual search prompts and directly navigate to first town
first_town = selected_towns[0]
first_town_url = get_town_url(first_town)
print(f"Navigating to {first_town}...")
driver.get(first_town_url)

# Wait for the page to load and listings to appear
try:
    WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "div.smallListingCardBodyWrap"))
    )
    print("✅ Page loaded successfully")
except TimeoutException:
    print("⚠️ Warning: Listings not found immediately, but continuing...")

# Start timing
start_time = time.time()

agent_data = []
listing_counts = defaultdict(int)

# Setup timestamped filename
filename = os.path.join(scrapes_dir, f"agents_browser_scrape_{datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.csv")

# Helper function to parse relative time
from dateutil.relativedelta import relativedelta
from dateutil.parser import parse as date_parse

def parse_posted_time(relative_time):
    now = datetime.datetime.now().replace(minute=0, second=0, microsecond=0)
    number = int(re.search(r'\d+', relative_time).group()) if re.search(r'\d+', relative_time) else 0
    if 'hour' in relative_time:
        return (now - datetime.timedelta(hours=number)).strftime('%Y-%m-%d %H:00')
    elif 'minute' in relative_time:
        return (now - datetime.timedelta(minutes=number)).strftime('%Y-%m-%d %H:00')
    elif 'day' in relative_time:
        return (now - datetime.timedelta(days=number)).strftime('%Y-%m-%d %H:00')
    elif 'week' in relative_time:
        return (now - datetime.timedelta(weeks=number)).strftime('%Y-%m-%d %H:00')
    elif 'month' in relative_time:
        return (now - relativedelta(months=number)).strftime('%Y-%m-%d %H:00')
    elif 'year' in relative_time:
        return (now - relativedelta(years=number)).strftime('%Y-%m-%d %H:00')
    return now.strftime('%Y-%m-%d %H:00')

def extract_json_ld_data(driver):
    try:
        # Find the JSON-LD script tag
        script = driver.find_element(By.CSS_SELECTOR, 'script[type="application/ld+json"]')
        # Parse the JSON data
        json_data = json.loads(script.get_attribute('innerHTML'))
        
        # Extract location hierarchy from BreadcrumbList
        if json_data and isinstance(json_data, dict) and json_data.get('@type') == 'BreadcrumbList':
            locations = []
            item_list = json_data.get('itemListElement', [])
            if isinstance(item_list, list):
                for item in item_list:
                    if isinstance(item, dict) and item.get('@type') == 'ListItem':
                        name = item.get('name')
                        if name:
                            locations.append(name)
            return locations
    except Exception as e:
        print(f"Error extracting JSON-LD data: {e}")
        return []

def scrape_listing(driver, url, town, retry_count=0, max_retries=2):
    """Scrape data from a single listing URL with retry capability"""
    try:
        # Add a small random delay between 1-3 seconds before visiting listing
        time.sleep(1 + (1 * retry_count))
        
        driver.get(url)
        # Use explicit wait instead of sleep
        try:
            WebDriverWait(driver, 8).until(
                EC.presence_of_element_located((By.ID, "listingAddress"))
            )
        except TimeoutException:
            if retry_count < max_retries:
                print(f"⚠️ Timeout waiting for listing page to load. Retry {retry_count+1}/{max_retries}...")
                return scrape_listing(driver, url, town, retry_count + 1, max_retries)
            else:
                return None

        try:
            agent_name = driver.find_element(By.CLASS_NAME, "realtorCardName").text
        except:
            agent_name = ""

        try:
            phone = driver.find_element(By.CLASS_NAME, "realtorCardContactNumber").text
        except:
            phone = ""

        try:
            email = driver.find_element(By.CLASS_NAME, "agent-email").get_attribute("href").replace("mailto:", "")
        except:
            email = ""

        try:
            website_elem = driver.find_element(By.CSS_SELECTOR, "a.realtorCardWebsite")
            website = website_elem.get_attribute("href")
        except:
            website = ""

        try:
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.ID, "listingPrice"))
            )
            price_wrapper = driver.find_element(By.ID, "listingPrice")
            price = price_wrapper.text
        except:
            price = ""

        try:
            address = driver.find_element(By.ID, "listingAddress").text.replace("\n", " ")
        except:
            address = ""

        try:
            posted_raw = driver.find_element(By.CLASS_NAME, "ConditionallyTimeOnRealtorCon").text.strip()
            posted = parse_posted_time(posted_raw)
        except:
            posted = ""

        # Clean the street address
        cleaned_address = address.split(',')[0].strip().title() if address else ""

        try:
            photo_text = driver.find_element(By.ID, "btnPhotoCount").text
            num_photos = photo_text.replace("+", "").strip()
        except:
            num_photos = ""

        # Get brokerage name
        try:
            brokerage = driver.find_element(By.CSS_SELECTOR, "div.officeCardName").text.strip()
        except:
            brokerage = ""

        first_name = agent_name.split()[0].capitalize() if agent_name else ""
        last_name = agent_name.split()[-1].capitalize() if agent_name and len(agent_name.split()) > 1 else ""
        full_name_key = f"{first_name} {last_name}"
        listing_counts[full_name_key] += 1

        return {
            "First Name": first_name,
            "Last Name": last_name,
            "Email": email,
            "Phone": phone,
            "Website": website,
            "Price": price,
            "Number of Listings": listing_counts[full_name_key],
            "Number of Photos": num_photos,
            "Street Address": cleaned_address,
            "Date Posted": posted,
            "Listing URL": url,
            "Town": town,
            "Brokerage": brokerage
        }
    except Exception as e:
        print(f"❌ Error scraping listing {url}: {e}")
        return None

try:
    for town_index, town in enumerate(selected_towns):
        print(f"\n{'='*50}")
        print(f"🌆 TOWN {town_index+1}/{len(selected_towns)}: {town}")
        print(f"{'='*50}")
        
        # Before switching to a new town, clear browser state
        if town_index > 0:  # Only for second town onwards
            try:
                print("🧹 Clearing browser state before switching towns...")
                # Clear cookies and cache
                driver.delete_all_cookies()
                driver.execute_script("window.localStorage.clear();")
                driver.execute_script("window.sessionStorage.clear();")
                # Close all tabs except the first one
                if len(driver.window_handles) > 1:
                    current_handle = driver.current_window_handle
                    for handle in driver.window_handles:
                        if handle != current_handle:
                            driver.switch_to.window(handle)
                            driver.close()
                    driver.switch_to.window(driver.window_handles[0])
            except Exception as e:
                print(f"⚠️ Error clearing browser state: {str(e)[:100]}...")
        
        # Switch to the current town
        if not switch_to_town(driver, town):
            print(f"❌ Failed to switch to {town} after multiple attempts. Moving to next town.")
            # Try with a new browser instance before giving up
            try:
                print("🔄 Trying with a fresh browser instance...")
                driver.quit()
            except:
                pass
            
            driver = setup_browser()
            if not switch_to_town(driver, town):
                print(f"❌ Still failed to switch to {town}. Skipping to next town.")
                continue
        
        # Add a small delay after switching towns
        time.sleep(2)
        
        # Re-verify we're on the correct town page
        print(f"🔍 Double-checking we're on {town} page...")
        try:
            current_url = driver.current_url
            page_text = driver.find_element(By.CSS_SELECTOR, "body").text
            
            if town.lower() not in current_url.lower() and town not in page_text:
                print(f"⚠️ Warning: May not be on {town} page. URL: {current_url[:50]}...")
                
                # Try one more time with a hard refresh
                print("🔄 Attempting hard refresh...")
                driver.get(get_town_url(town))
                wait_for_page_ready(driver, timeout=15)
                wait_for_listings(driver, timeout=15)
        except Exception as e:
            print(f"⚠️ Error during final verification: {str(e)[:100]}...")

        # First, collect all URLs for the town
        print(f"\n📥 Collecting all listing URLs for {town}...")
        all_listing_urls = []
        page_number = 1
        consecutive_empty_pages = 0
        max_consecutive_empty = 3

        while page_number <= max_pages:
            try:
                print(f"Collecting URLs from page {page_number} in {town}...")
                
                # Wait for listings to appear
                if not wait_for_listings(driver):
                    print(f"⚠️ No listings found on page {page_number} in {town}")
                    consecutive_empty_pages += 1
                    if consecutive_empty_pages >= max_consecutive_empty:
                        print(f"⚠️ No listings found for {consecutive_empty_pages} consecutive pages in {town}. Moving to next town.")
                        break
                    
                    # Try to navigate to next page even if no listings found
                    if not navigate_to_next_page(driver):
                        print(f"⚠️ Cannot navigate to next page. Moving to next town.")
                        break
                    page_number += 1
                    continue

                # Get URLs from current page
                page_urls = get_listing_urls(driver)
                if page_urls:
                    all_listing_urls.extend(page_urls)
                    print(f"✅ Found {len(page_urls)} URLs on page {page_number}")
                    consecutive_empty_pages = 0
                else:
                    consecutive_empty_pages += 1
                    if consecutive_empty_pages >= max_consecutive_empty:
                        print(f"⚠️ No listings found for {consecutive_empty_pages} consecutive pages in {town}. Moving to next town.")
                        break

                # Navigate to next page with retry logic
                if not navigate_to_next_page(driver):
                    print(f"⚠️ End of pages for {town}. Moving to next town.")
                    break
                
                # Add delay between page switches
                time.sleep(2)
                
                # Increment page number
                page_number += 1
                
            except Exception as e:
                print(f"❌ Error collecting URLs on page {page_number}: {str(e)[:100]}...")
                # Try to move to next page or town
                try:
                    if not navigate_to_next_page(driver):
                        print(f"⚠️ Cannot continue with {town}. Moving to next town.")
                        break
                    page_number += 1
                except:
                    print(f"⚠️ Cannot recover. Moving to next town.")
                    break

        print(f"\n📊 Collected {len(all_listing_urls)} total URLs for {town}")
        
        # Now process all collected URLs
        if all_listing_urls:
            print(f"\n🔄 Processing {len(all_listing_urls)} listings for {town}...")
            consecutive_listing_errors = 0

            for i, url in enumerate(all_listing_urls, 1):
                try:
                    print(f"→ Processing listing {i}/{len(all_listing_urls)}")
                    
                    listing_data = scrape_listing(driver, url, town)
                    
                    if listing_data:
                        agent_data.append(listing_data)
                        print(f"✅ Successfully scraped listing {i}/{len(all_listing_urls)} in {town} - {listing_data.get('Street Address', 'No address')}")
                        consecutive_listing_errors = 0  # Reset error counter on success
                    else:
                        consecutive_listing_errors += 1
                        print(f"⚠️ Failed to scrape listing {i}/{len(all_listing_urls)} - Error counter: {consecutive_listing_errors}/{max_consecutive_errors}")
                    
                    # Check if we need to restart the browser due to too many errors
                    if consecutive_listing_errors >= max_consecutive_errors:
                        print(f"🔄 Too many consecutive listing failures ({consecutive_listing_errors}). Restarting browser...")
                        try:
                            driver.quit()
                        except:
                            print("⚠️ Error while closing browser")
                            
                        # Save data so far
                        if agent_data:
                            df = pd.DataFrame(agent_data)
                            df.to_csv(filename, index=False)
                            print(f"💾 Saved data before browser restart")
                        
                        # Create new browser instance
                        driver = setup_browser()
                        
                        # Navigate back to the first page of current town
                        print(f"Navigating to {town} after browser restart...")
                        driver.get(get_town_url(town))
                        wait_for_page_ready(driver)
                        
                        # Reset error counter
                        consecutive_listing_errors = 0
                    
                    # Auto-save after every 10 listings
                    if i % 10 == 0 and agent_data:
                        df = pd.DataFrame(agent_data)
                        df.to_csv(filename, index=False)
                        print(f"💾 Auto-saved after {i} listings")
                    
                except Exception as e:
                    consecutive_listing_errors += 1
                    print(f"❌ Error processing listing {i}: {str(e)[:100]}...")
                    print(f"⚠️ Error counter: {consecutive_listing_errors}/{max_consecutive_errors}")
                    
                    # Check if we need to restart the browser
                    if consecutive_listing_errors >= max_consecutive_errors:
                        print(f"🔄 Too many consecutive errors ({consecutive_listing_errors}). Restarting browser...")
                        try:
                            driver.quit()
                        except:
                            print("⚠️ Error while closing browser")
                            
                        # Save data so far
                        if agent_data:
                            df = pd.DataFrame(agent_data)
                            df.to_csv(filename, index=False)
                            print(f"💾 Saved data before browser restart")
                            
                        # Create new browser instance
                        driver = setup_browser()
                        
                        # Navigate back to the first page of current town
                        print(f"Navigating to {town} after browser restart...")
                        driver.get(get_town_url(town))
                        wait_for_page_ready(driver)
                        
                        # Reset error counter
                        consecutive_listing_errors = 0

        # Save data after processing all listings for the town
        if agent_data:
            df = pd.DataFrame(agent_data)
            df.to_csv(filename, index=False)
            print(f"💾 Saved data for {town} to {filename}")

except KeyboardInterrupt:
    print("🛑 Scraper interrupted by user.")
except Exception as e:
    print(f"❌ An error occurred: {str(e)[:200]}...")
    # Save any data we've collected so far
    if agent_data:
        df = pd.DataFrame(agent_data)
        df.to_csv(filename, index=False)
        print(f"💾 Saved partial data to {filename}")
finally:
    # Always try to save data at the end
    if agent_data:
        try:
            df = pd.DataFrame(agent_data)
            df.to_csv(filename, index=False)

            # Calculate and display timing information
            end_time = time.time()
            duration_minutes = (end_time - start_time) / 60
            total_listings = len(agent_data)
            print(f"✅ Final data saved to {filename}")
            print(f"⏱️ Scraped {total_listings} listings in {duration_minutes:.1f} minutes")
        except Exception as save_error:
            print(f"❌ Error saving final data: {save_error}")
    else:
        print("⚠️ No data was collected during the scraping session.")

    # Close the browser
    try:
        driver.quit()
    except:
        print("⚠️ Browser may have already closed.")
