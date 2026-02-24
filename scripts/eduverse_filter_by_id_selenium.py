#!/usr/bin/env python3
"""
Optional: use Selenium to open app.eduverse.kz participant page, type user_id in search, click Filter.

Usage:
  pip install selenium webdriver-manager
  # Log in to app.eduverse.kz in the same browser profile, or pass credentials and implement login.
  python eduverse_filter_by_id_selenium.py 83807

Or run with a visible browser (default). You must be already logged in to app.eduverse.kz in that profile,
or the script can use a profile where you've logged in once.
"""
import sys
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

PARTICIPANT_URL = "https://app.eduverse.kz/default/participant"


def main():
    if len(sys.argv) < 2:
        print("Usage: python eduverse_filter_by_id_selenium.py <user_id_or_participant_id>")
        sys.exit(1)
    search_id = sys.argv[1].strip()

    try:
        from webdriver_manager.chrome import ChromeDriverManager
        from selenium.webdriver.chrome.service import Service
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service)
    except Exception:
        driver = webdriver.Chrome()

    try:
        driver.get(f"{PARTICIPANT_URL}?id={search_id}")
        wait = WebDriverWait(driver, 15)
        # Wait for the filter form and search input
        search_input = wait.until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "form input[type=text]"))
        )
        search_input.clear()
        search_input.send_keys(search_id)
        search_input.send_keys("\t")  # blur / trigger Angular
        # Click the Filter button (icon fa-filter inside form)
        filter_btn = driver.find_element(By.CSS_SELECTOR, "form .fa-filter")
        parent = filter_btn.find_element(By.XPATH, "./ancestor::button | ./ancestor::app-button")
        parent.click()
        print("Filter clicked. Leave the browser open or close it.")
        input("Press Enter to close the browser...")
    finally:
        driver.quit()


if __name__ == "__main__":
    main()
