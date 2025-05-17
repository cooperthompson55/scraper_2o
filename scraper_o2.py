import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
import time
import pandas as pd
import re
import json
from collections import defaultdict
import datetime

# Set up undetected Chrome driver (visible mode)
driver = uc.Chrome()
driver.maximize_window()

# Go to Realtor.ca
print("Opening Realtor.ca...")
driver.get("https://www.realtor.ca")

# Ask user to do the search manually
input("🔎 Please search manually in the browser, then press Enter here to continue...")
input("✅ Once listings appear in the left sidebar, press Enter to start scraping...")

agent_data = []
listing_counts = defaultdict(int)
page_number = 1
max_pages = 50

# Setup timestamped filename
filename = f"agents_browser_scrape_{datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.csv"

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

try:
    while page_number <= max_pages:
        print(f"Scraping page {page_number}...")
        
        # Wait for listings to load
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "div.smallListingCardBodyWrap"))
        )
        listing_cards = driver.find_elements(By.CSS_SELECTOR, "div.smallListingCardBodyWrap")[:12]
        listing_count = len(listing_cards)
        print(f"✅ Found {listing_count} listings on page {page_number}.")

        for i in range(listing_count):
            try:
                print(f"→ Page {page_number}, Listing {i+1}")
                card = listing_cards[i]
                driver.execute_script("arguments[0].scrollIntoView(true);", card)
                time.sleep(1)
                card.click()
                time.sleep(5)

                driver.switch_to.window(driver.window_handles[-1])
                listing_url = driver.current_url

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

                first_name = agent_name.split()[0].capitalize() if agent_name else ""
                last_name = agent_name.split()[-1].capitalize() if agent_name else ""
                full_name_key = f"{first_name} {last_name}"
                listing_counts[full_name_key] += 1

                agent_data.append({
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
                    "Listing URL": listing_url
                })

                driver.close()
                driver.switch_to.window(driver.window_handles[0])
                time.sleep(2)
            except Exception as e:
                print(f"❌ Error scraping listing {i+1} on page {page_number}: {e}")
                with open("errors.log", "a") as log:
                    log.write(f"Page {page_number}, Listing {i+1} Error: {e}\n")
                driver.switch_to.window(driver.window_handles[0])

        # Auto-save after each page
        df = pd.DataFrame(agent_data)
        df.to_csv(filename, index=False)
        print(f"💾 Auto-saved page {page_number} to {filename}")

        try:
            next_button = driver.find_element(By.CSS_SELECTOR, "div.paginationLinkText i.fa-angle-right")
            driver.execute_script("arguments[0].scrollIntoView(true);", next_button)
            next_button.click()
            page_number += 1
            time.sleep(5)
        except:
            print("🚫 No more pages found.")
            break

except KeyboardInterrupt:
    print("🛑 Scraper interrupted by user.")

# Final save
df = pd.DataFrame(agent_data)
df.to_csv(filename, index=False)
print(f"✅ Final data saved to {filename}")

# Close the browser
driver.quit()
