"""
Step 1: Scrape scholarships from CareerOneStop.

Refactored from src/careerstop.py — same logic, but wrapped as an
importable function instead of a script with a hardcoded call at the bottom.
"""

import json
import os
from tqdm import tqdm
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
from core.config import SCHOLARSHIPS_PATH


def _scholarship_key(s):
    """Unique key for a scholarship: (Title, Organization)."""
    title = s.get("Title", "").strip().lower()
    org = s.get("Organization", "").strip().lower()
    return (title, org)


def _save_json(path: str, data: list) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)


def scrape(start_month: str, end_month: str, output_path: str = None, timeout: int = 800, force_rescrape: bool = False) -> list:
    """Scrape CareerOneStop scholarships between start_month (exclusive) and
    end_month (exclusive). Scholarships whose deadline falls in start_month are
    skipped; scraping stops when end_month is encountered.

    Writes each scholarship to output_path immediately after it is scraped.
    Supports resume via dedup on (Title, Organization).
    
    Supports resume via dedup on (Title, Organization).

    Returns the list of all scraped scholarships.
    """
    if output_path is None:
        output_path = str(SCHOLARSHIPS_PATH)

    START = start_month.lower()
    END_MONTH = end_month.lower()
    TIMEOUT = timeout
    stop = False
    url = "https://www.careeronestop.org/Toolkit/Training/find-scholarships.aspx?&pagesize=500&curpage=1"

    # Load any scholarships already saved (supports resume + dedup).
    if os.path.exists(output_path):
        with open(output_path, "r", encoding="utf-8") as f:
            try:
                current = json.load(f)
            except json.JSONDecodeError:
                current = []
    else:
        current = []

    if current:
        tqdm.write(f"Loaded {len(current)} cached scholarships from {output_path} for deduplication.")

    seen_keys = {_scholarship_key(s) for s in current}

    with sync_playwright() as p:
        browser = p.webkit.launch(headless=True)
        page = browser.new_page()
        page.goto(url)
        try:
            page.wait_for_selector('ul.cos-pagination', timeout=10000)
        except PlaywrightTimeoutError:
            pass
        page.wait_for_timeout(TIMEOUT)

        pagination = page.locator('ul.cos-pagination a')
        pages = [text for text in pagination.all_text_contents() if text.isdigit()]
        page.close()

        for page_num in range(1, int(pages[-1]) + 1):
            tqdm.write(f"Page {page_num}:")
            np = browser.new_page()
            parts = url.split("=")
            page_url = f"{parts[0]}={parts[1]}={page_num}"
            np.goto(page_url)
            try:
                np.wait_for_selector('a[title="Click here for detail information"]', timeout=10000)
            except PlaywrightTimeoutError:
                pass
            np.wait_for_timeout(TIMEOUT)

            detail_links = np.locator('a[title="Click here for detail information"]')
            hrefs = [
                "https://www.careeronestop.org" + detail_links.nth(j).get_attribute("href")
                for j in range(detail_links.count())
            ]
            np.close()

            for href in tqdm(hrefs):
                nnp = browser.new_page()
                try:
                    nnp.goto(href, timeout=30000)
                    try:
                        nnp.wait_for_selector('table.cos-table-detail', timeout=10000)
                    except PlaywrightTimeoutError:
                        pass
                    nnp.wait_for_timeout(TIMEOUT)
                except PlaywrightTimeoutError:
                    tqdm.write(f"\n  ✗ Timeout, skipping: {href}")
                    nnp.close()
                    continue
                except Exception as e:
                    tqdm.write(f"\n  ✗ Error, skipping {href}: {e}")
                    nnp.close()
                    continue

                title = nnp.locator('th[id="detailTitle"]').inner_text().strip()
                scholarship_info = {
                    "Title": title,
                    "Link": href
                }

                rows = nnp.locator("table.cos-table-detail tbody tr").all()
                for row in rows:
                    key = row.locator("td").nth(0).inner_text().strip()
                    val_td = row.locator("td").nth(1)

                    anchor = val_td.locator("a")
                    if anchor.count() > 0:
                        anchor_href = anchor.get_attribute("href") or ""
                        anchor_text = anchor.inner_text().strip()

                        if anchor_href.startswith("mailto:"):
                            anchor_href = anchor_href.replace("mailto:", "").split("<")[0].strip()
                        if anchor_href.startswith("Email:"):
                            anchor_href = anchor_href.replace("Email:", "")

                        val_td_info = {"text": anchor_text, "url": anchor_href}
                    else:
                        lines = [line.strip() for line in val_td.inner_text().split("\n") if line.strip()]
                        val_td_info = "\n".join(lines) if len(lines) > 1 else (lines[0] if lines else "")

                    scholarship_info[key] = val_td_info

                nnp.close()

                # Month-range filter
                try:
                    deadline_lower = scholarship_info["Deadline"].lower()
                    if END_MONTH in deadline_lower:
                        stop = True
                        break
                    if START in deadline_lower:
                        continue
                except KeyError:
                    pass

                key = _scholarship_key(scholarship_info)
                if key in seen_keys:
                    continue
                seen_keys.add(key)
                current.append(scholarship_info)
                _save_json(output_path, current)

            if stop:
                break

    tqdm.write(f"Done — {len(current)} scholarships saved to {output_path}.")
    return current
