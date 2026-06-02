from playwright.sync_api import sync_playwright
import json
from tqdm import tqdm

def discovery(month, timeout=750):
    MONTH = month
    TIMEOUT = timeout
    END = False
    url = "https://www.careeronestop.org/Toolkit/Training/find-scholarships.aspx?&pagesize=500&curpage=1"

    scholarships = []

    with sync_playwright() as p:
        browser = p.webkit.launch(headless=True)
        page = browser.new_page()
        page.goto(url)

        page.wait_for_timeout(TIMEOUT)

        content = page.content()

        links = page.locator('ul.cos-pagination a')
        pages = [text for text in links.all_text_contents() if text.isdigit()]

        page.close()

        for i in range(1, int(pages[-1]) + 1):
            print(f"Page {i}:")
            np = browser.new_page()
            parts = url.split("=")
            url = f"{parts[0]}={parts[1]}={i}"
            np.goto(url)

            np.wait_for_timeout(TIMEOUT)

            links = np.locator('a[title="Click here for detail information"]')
            hrefs = [("https://www.careeronestop.org" + links.nth(i).get_attribute("href")) for i in range(links.count())]

            np.close()

            for link in tqdm(hrefs):
                nnp = browser.new_page()
                nnp.goto(link)
                nnp.wait_for_timeout(TIMEOUT)
                title = nnp.locator('th[id="detailTitle"]').inner_text().strip()
                scholarship_info = {
                    "Title": title
                }
                rows = nnp.locator("table.cos-table-detail tbody tr").all()
                for row in rows:
                    key = row.locator("td").nth(0).inner_text().strip()
                    val_td = row.locator("td").nth(1)
                    
                    link = val_td.locator("a")
                    if link.count() > 0:
                        href = link.get_attribute("href") or ""
                        text = link.inner_text().strip()
                        
                        if href.startswith("mailto:"):
                            href = href.replace("mailto:", "").split("<")[0].strip()
                        
                        if href.startswith("Email:"):
                            href = href.replace("Email:", "")
                            
                        val_td_info = {
                            "text": text,
                            "url": href
                        }
                    else:
                        lines = [line.strip() for line in val_td.inner_text().split("\n") if line.strip()]
                        val_td_info = "\n".join(lines) if len(lines) > 1 else (lines[0] if lines else "")
                    scholarship_info[key] = val_td_info
                
                nnp.close()
                try:
                    if MONTH in scholarship_info["Deadline"].lower():
                        END = True
                        break
                except KeyError:
                    pass
                scholarships.append(scholarship_info)
            
            if END:
                break

    with open("scholarships.json", "w", encoding="utf-8") as f:
        json.dump(scholarships, f, indent=4, ensure_ascii=False)