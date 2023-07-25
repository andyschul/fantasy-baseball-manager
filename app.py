import logging
from collections import Counter
from typing import List, Dict, Tuple
import time
import os
from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from apscheduler.schedulers.blocking import BlockingScheduler
from selenium.webdriver.chrome.options import Options
from selenium import webdriver

# Setup logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Constants
PROBABLE_PITCHER_XPATH = './/strong[@title="Probable Pitcher"]'
PITCHER_ROWS_XPATH = '//*[@id="fitt-analytics"]/div/div[5]/div[2]/div[3]/div/div/div/div[3]/div/div[2]/div/div/table/tbody/tr'
NUM_STARTING_PITCHER_SLOTS = 6

class FantasyBaseballManager:
    def __init__(self):
        self.username: str = os.getenv('FANTASY_USERNAME')
        self.password: str = os.getenv('FANTASY_PASSWORD')
        self.team_page_url: str = os.getenv('TEAM_PAGE_URL')
        self.driver: webdriver.Chrome = self.create_driver()

    def create_driver(self) -> webdriver.Firefox:
        chrome_options = Options()
        chrome_options.add_argument("--headless=new")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_prefs = {}
        chrome_options.experimental_options["prefs"] = chrome_prefs
        chrome_prefs["profile.default_content_settings"] = {"images": 2}
        driver = webdriver.Chrome(options=chrome_options)
        return driver

    def login_to_website(self) -> None:
        self.driver.get(self.team_page_url)
        WebDriverWait(self.driver, 60).until(EC.frame_to_be_available_and_switch_to_it((By.ID, "oneid-iframe")))
        WebDriverWait(self.driver, 60).until(EC.element_to_be_clickable((By.ID, "InputLoginValue"))).send_keys(self.username)
        WebDriverWait(self.driver, 60).until(EC.element_to_be_clickable((By.ID, "InputPassword"))).send_keys(self.password)
        WebDriverWait(self.driver, 60).until(EC.element_to_be_clickable((By.ID, "BtnSubmit"))).click()
        time.sleep(10)

    def get_empty_slots(self) -> List[int]:
        rows = self.driver.find_elements_by_xpath(PITCHER_ROWS_XPATH)
        return [i for i, row in enumerate(rows[:NUM_STARTING_PITCHER_SLOTS]) if not row.find_elements_by_xpath('.//button')]

    def get_pitchers(self) -> List[Dict[str, int]]:
        pitchers_array: List[Dict[str, int]] = []
        rows = self.driver.find_elements_by_xpath(PITCHER_ROWS_XPATH)
        for i, row in enumerate(rows):
            if row.find_elements_by_xpath(PROBABLE_PITCHER_XPATH):
                pitchers_array.append({'priority': 1})
            else:
                try:
                    priority = 2 if row.find_element_by_class_name('playerinfo__playerpos').text == 'RP' else 3
                except:
                    priority = 100
                pitchers_array.append({'priority': priority})
        return pitchers_array

    def find_minimum_swaps(self, pitchers_array: List[Dict[str, int]]) -> List[Tuple[int, int]]:
        priorities = [pitcher['priority'] for pitcher in pitchers_array]
        required_priorities = Counter(sorted(priorities)[:NUM_STARTING_PITCHER_SLOTS])
        swaps: List[Tuple[int, int]] = []
        for i in range(NUM_STARTING_PITCHER_SLOTS):
            if required_priorities[pitchers_array[i]['priority']] > 0:
                required_priorities[pitchers_array[i]['priority']] -= 1
            else:
                for j in range(NUM_STARTING_PITCHER_SLOTS, len(pitchers_array)):
                    if required_priorities[pitchers_array[j]['priority']] > 0:
                        required_priorities[pitchers_array[j]['priority']] -= 1
                        swaps.append((i, j))
                        pitchers_array[i], pitchers_array[j] = pitchers_array[j], pitchers_array[i]
                        break
        return swaps

    def click_buttons_in_rows(self, rows: List[webdriver.Firefox], pos: List[int], delay: int = 5) -> None:
        for i in pos:
            button = rows[i].find_element_by_tag_name('button')
            button.click()
            time.sleep(delay)

    def swap_empty(self, empty_starting_slots: List[int]) -> None:
        rows = self.driver.find_elements_by_xpath(PITCHER_ROWS_XPATH)
        for slot in empty_starting_slots:
            self.click_buttons_in_rows(rows, [NUM_STARTING_PITCHER_SLOTS + 1, slot])
        time.sleep(5)

    def swap_pitchers(self, swaps: List[Tuple[int, int]]) -> None:
        rows = self.driver.find_elements_by_xpath(PITCHER_ROWS_XPATH)
        for swap in swaps:
            self.click_buttons_in_rows(rows, [swap[0], swap[1]])
        time.sleep(5)

    def run(self) -> None:
        try:
            logger.info('logging in')
            self.login_to_website()
            self.driver.get(self.team_page_url)
            time.sleep(10)

            logger.info('getting empty slots')
            empty_starting_slots = self.get_empty_slots()
            logger.info(f'Empty starting slots: {empty_starting_slots}')
            if empty_starting_slots:
                logger.info('swapping empty slots')
                self.swap_empty(empty_starting_slots)

            logger.info('getting pitchers')
            pitchers_array = self.get_pitchers()
            logger.info('getting positions to swap')
            positions_to_swap = self.find_minimum_swaps(pitchers_array)
            logger.info(f'Positions to swap: {positions_to_swap}')
            if positions_to_swap:
                logger.info('swapping pitchers')
                self.swap_pitchers(positions_to_swap)
        except Exception as e:
            logger.error(f'An error occurred: {e}')
        finally:
            self.driver.quit()

def scheduled_job() -> None:
    logger.info('Running job...')
    manager = FantasyBaseballManager()
    manager.run()
    logger.info('Job completed.')

scheduler = BlockingScheduler()
scheduler.add_job(scheduled_job, 'cron', day_of_week='mon-sun', hour=10, timezone='US/Eastern')

logger.info('Starting the scheduler...')
scheduler.start()
