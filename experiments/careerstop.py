'''
Legacy Experiment: careerstop.py

Purpose:
An experimental scraper specifically designed to extract data from CareerOneStop.

Capabilities:
- Uses Playwright to paginate through CareerOneStop's scholarship table.
- Visits individual detail pages and extracts basic fields (Title, Link, and table rows).

What it lacked:
- Extremely slow due to synchronous playwright usage and deep page navigation.
- Prone to timeouts and anti-bot blocking.
- Failed to extract the deep, unstructured text needed for the LLM pipeline, capturing mostly shallow table data.
- Abandoned in favor of a faster, more robust scraping approach.
'''
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
import json
import os
from tqdm import tqdm


def _scholarship_key(s):
    """Unique key for a scholarship: (Title, Organization)."""
    title = s.get("Title", "").strip().lower()
    org = s.get("Organization", "").strip().lower()
    return (title, org)


def _save_json(path: str, data: list) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)


def discovery(start_month, end_month, output_path="current_scholarships.json", timeout=800):
    """Scrape CareerOneStop scholarships between start_month (exclusive) and
    end_month (exclusive). Scholarships whose deadline falls in start_month are
    skipped; scraping stops when end_month is encountered.

    Writes each scholarship to output_path immediately after it is scraped.
    Each run starts fresh — only scholarships from THIS run are stored.
    """
    START = start_month.lower()
    END_MONTH = end_month.lower()
    TIMEOUT = timeout
    stop = False
    url = "https://www.careeronestop.org/Toolkit/Training/find-scholarships.aspx?&pagesize=500&curpage=1"

    # Load any scholarships already saved in this run (supports resume + dedup).
    if os.path.exists(output_path):
        with open(output_path, "r", encoding="utf-8") as f:
            try:
                current = json.load(f)
            except json.JSONDecodeError:
                current = []
    else:
        current = []

    seen_keys = {_scholarship_key(s) for s in current}

    with sync_playwright() as p:
        browser = p.webkit.launch(headless=True)
        page = browser.new_page()
        page.goto(url)
        page.wait_for_timeout(TIMEOUT)

        pagination = page.locator('ul.cos-pagination a')
        pages = [text for text in pagination.all_text_contents() if text.isdigit()]
        page.close()

        for page_num in range(1, int(pages[-1]) + 1):
            print(f"Page {page_num}:")
            np = browser.new_page()
            parts = url.split("=")
            page_url = f"{parts[0]}={parts[1]}={page_num}"
            np.goto(page_url)
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
                    nnp.wait_for_timeout(TIMEOUT)
                except PlaywrightTimeoutError:
                    print(f"\n  ✗ Timeout, skipping: {href}")
                    nnp.close()
                    continue
                except Exception as e:
                    print(f"\n  ✗ Error, skipping {href}: {e}")
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

                # ----------------------------------------------------------
                # Month-range filter:
                #   • deadline in START month  → skip (exclusive lower bound)
                #   • deadline in END_MONTH    → stop scraping (exclusive upper bound)
                # ----------------------------------------------------------
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
                    continue  # already scraped this scholarship
                seen_keys.add(key)
                current.append(scholarship_info)
                _save_json(output_path, current)

            if stop:
                break

    print(f"Done — {len(current)} scholarships saved to {output_path}.")


discovery("july", "september")