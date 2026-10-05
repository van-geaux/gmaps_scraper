from bs4 import BeautifulSoup
from datetime import datetime

from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from src.logger import logger

import aiohttp
import asyncio
import json
import re
import sqlite3
import sys
import time

from aiohttp import ClientTimeout, ClientError, ClientConnectorError

async def fetch(session, google_url, proxy_detail, name, retries=10):
    timeout = ClientTimeout(total=10)
    for attempt in range(retries+2):
        try:
            async with session.get(google_url, proxy=proxy_detail, ssl=False, timeout=timeout) as response:
                if attempt > retries:
                    logger.warning(f'All 10 attempts failed for "{name}"')
                    logger.warning(f'Please check network connectivity')
                    sys.exit(1)

                response.raise_for_status()

                if attempt > 0:
                    logger.info(f'Retry attempt succeeded for "{name}"')

                return await response.text()
            
        except (ClientError, ClientConnectorError) as e:
            logger.info(f'Request failed for "{name}": {e}')
            logger.info(f'Retry attempt {attempt + 1} for "{name}"...')
            await asyncio.sleep(1)
        except Exception as e:
            logger.error(f'An unexpected error occurred for "{name}": {e}')
            logger.info(f'Retry attempt {attempt + 1} for "{name}"...')
            await asyncio.sleep(1)
    return None

async def process_target(session, target, proxy_detail, ward, district, city, province, category, search_id, dbtime):
    try:
        name = target.find_all("div", {'class':True})[0].find('a')['aria-label']
        if name == "..":
            return ("..", "..", "..", "..", 0, 0, "..", "..", ward, district, city, province, category, search_id, dbtime)

        try:
            rating = float(target.find_all('span')[4].find_all('span')[0].text.strip().replace(',', '.'))
        except:
            rating = 0

        try:
            rating_count = int(target.find_all("div")[17].find_all("span")[4].text.strip()[1:-1].replace(',', ''))
        except:
            rating_count = 0

        google_url = target.find_all('a')[0]['href']

        try:
            logger.info(f'Getting location data for "{name}"')

            logger.debug('Using remote Selenium driver')
            search_data_deep = await fetch(session, google_url, proxy_detail, name)

            if not search_data_deep:
                raise ValueError("No data received")

            search_soup_deep = BeautifulSoup(search_data_deep, 'html.parser')
            scripts_deep = search_soup_deep.find_all('script')

            for script_deep in scripts_deep:
                if 'window.APP_INITIALIZATION_STATE' in str(script_deep):
                    data_deep = str(script_deep).split('=', 3)[3]
                    data2_deep = data_deep.rsplit(';', 10)[0].split(";window.APP_")[1].split("INITIALIZATION_STATE=")[1]
                    json_data_deep = json.loads(data2_deep)
                    type_deep = json_data_deep[3][-1][5:]
                    json_result_deep = json.loads(type_deep)
                    break

        except Exception as e:
            json_result_deep = ''
            logger.error(f'Getting location data for "{name}" failed: {e}')
        
        try:
            latitude = json_result_deep[6][9][2]
        except:
            try:
                coordinate = re.search(r'!3d(-?\d+\.\d+)!4d(-?\d+\.\d+)', target.find_all("div")[0].find("a")['href'])
                latitude = float(coordinate.group(1))
            except:
                latitude = ''

        try:
            longitude = json_result_deep[6][9][3]
        except:
            try:
                longitude = float(coordinate.group(2))
            except:
                longitude = ''
        
        try:
            address = json_result_deep[6][18]
        except:
            try:
                address = [span for span in target.find_all('span', {'aria-hidden':'', 'aria-label':'', 'class':''}) if not span.find('span')][1].text.strip()
            except:
                address = ''

        try:
            google_tag = str(json_result_deep[6][13]).strip('[').strip(']').replace('\'','')
        except:
            try:
                google_tag = [span for span in target.find_all('span', {'aria-label':'', 'aria-hidden':'', 'class':''}) if not span.find('span')][0].text.strip()
            except:
                google_tag = ''

        return (name, longitude, latitude, address, rating, rating_count, google_tag, google_url, ward, district, city, province, category, search_id, dbtime)
    except IndexError:
        return None
    except Exception as e:
        logger.error(e)
        raise

async def main(targets_no_ad, proxy_detail, ward, district, city, province, category, search_id, dbtime):
    try:
        async with aiohttp.ClientSession() as session:
            tasks = []
            for i in range(0, len(targets_no_ad)):
                target = targets_no_ad[i]

                task = process_target(session, target, proxy_detail, ward, district, city, province, category, search_id, dbtime)
                
                tasks.append(task)
            results = await asyncio.gather(*tasks)
        return [result for result in results if result is not None]
    except Exception as e:
        logger.error(e)
        raise

async def parent_query(i, driver, loglevel, df_search, ward, district, city, province, search_url, bar, start_time):
    try:
        logger.debug(f'Checking proxy availability')
        try:
            if loglevel.lower() == 'debug':
                driver.get("http://httpbin.org/ip")
                ip_element = driver.find_element(By.TAG_NAME, "body")
                current_ip = ip_element.text
                logger.debug(f"Current IP: {current_ip}")
        except:
            pass
        logger.debug(search_url)
        driver.get(search_url)
        WebDriverWait(driver, 10).until(EC.title_contains("Google Maps"))
        proxy_check = ''
    except Exception as e:
        logger.warning(
            "Remote Selenium navigation failed for %s: %r",
            search_url,
            e,
        )
        try:
            logger.warning(
                "Remote browser state: title=%r url=%r",
                driver.title,
                driver.current_url,
            )
        except Exception:
            pass
        proxy_check = 'Remote Selenium failed'
        targets_no_ad = 'break'
        return targets_no_ad, proxy_check
                    
    divSideBar = None
    for attempt, wait_seconds in enumerate((30, 20), start=1):
        try:
            divSideBar = WebDriverWait(driver, wait_seconds).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div[role='feed']"))
            )
            break
        except Exception as e:
            try:
                source = driver.page_source
                logger.warning(
                    "Google Maps feed not ready (attempt %s/2): %s; title=%r url=%r source_len=%s",
                    attempt,
                    type(e).__name__,
                    driver.title,
                    driver.current_url,
                    len(source),
                )
            except Exception:
                logger.warning("Google Maps feed not ready (attempt %s/2): %s", attempt, type(e).__name__)
            if attempt == 1:
                try:
                    driver.refresh()
                except Exception as refresh_error:
                    logger.warning("Google Maps refresh failed before retry: %r", refresh_error)

    if divSideBar is None:
        logger.info(f'[EMPTY] Query {i+1}/{len(df_search)} 0 data in {ward}, {district}, {city}, {province}')
        logger.info(f'Total time {time.time() - start_time}')
        print('')
        bar()
        targets_no_ad = 'continue'
        return targets_no_ad, proxy_check
                    
    keepScrolling=True
    try:
        logger.info(f'Query {i+1}/{len(df_search)} Getting data for {ward}, {district}, {city}, {province}')
        scroll_count = 0
        while keepScrolling:
            try:
                logger.debug(f'Page scroll')
                divSideBar.send_keys(Keys.PAGE_DOWN)
                div_html = driver.find_element(By.TAG_NAME, "html").get_attribute('outerHTML')
                scroll_count += 1

                if "You've reached the end of the list." in div_html or 'Anda telah mencapai akhir daftar.' in div_html:
                    keepScrolling=False
                    logger.info(f'Total scrolls: {scroll_count}')
            except Exception as e:
                logger.error(f'Page scroll failed: {e}')
    except:
        pass
                    
    try:
        logger.debug(f'Getting page html')
        search_soup = BeautifulSoup(driver.page_source, 'html.parser')
        targets = search_soup.find("div", {'role': 'feed'}).find_all('div', {'class': False})[:-1]
        targets_no_ad = [div for div in targets if div.find('div', {'jsaction':True})]
    except Exception as e:
        logger.error(f'Getting page html failed: {e}')
        targets_no_ad = None

    return targets_no_ad, proxy_check
