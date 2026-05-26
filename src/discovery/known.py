"""
scholarshipowl.com
https://bold.org/scholarships/
scholarships.com
careeronestop.org
bigfuture.collegeboard.org/scholarship-search
sallie.com
"""

from playwright.sync_api import sync_playwright
from ..llm import js

def bold(headless=True):
    url = "https://bold.org/scholarships/"
    with sync_playwright() as p:
        browser = p.webkit.launch(headless=headless)
        page = browser.new_page()
        page.goto(url)

        page.wait_for_timeout(5000)

        content = page.content()

        instructions = "toggles the no-essay only filter"
        page.evaluate(js(content, instructions))

        page.wait_for_timeout(5000)

        content = page.content()
        print(content)
        
        browser.close()

