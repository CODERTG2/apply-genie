'''
Legacy Experiment: filter.py (Root Version)

Purpose:
An experimental script to filter out fake or unusable scholarships before classification using LLM-based web verification.

Capabilities:
- Used `llmverifier.py` to visit the "For more information" URL of a scholarship.
- Asked an LLM to verify if the page was a legitimate scholarship application page.

What it lacked:
- Scraping every URL dynamically during the filter step was incredibly slow and error-prone (due to timeouts, 403s, and anti-bot protection).
- Replaced by a faster, heuristic-based filter in `src/steps/filter.py` that doesn't require live web scraping.
'''
import os
import sys
import json
from llmverifier import verify_scholarship_url
from tqdm import tqdm

def get_more_info_url(scholarship):
    """
    Extracts the URL from the 'For more information' field of a scholarship.
    Handles dictionary format (e.g. {"url": "...", "text": "..."}) and string format.
    Returns the URL string if present, non-empty, and valid; otherwise None.
    """
    info = scholarship.get("For more information") or scholarship.get("for_more_information")
    if not info:
        return None

    url = None
    if isinstance(info, dict):
        url = info.get("url") or info.get("text")
    elif isinstance(info, str):
        url = info

    if isinstance(url, str):
        url_str = url.strip()
        if url_str.startswith(("http://", "https://", "www.")):
            return url_str

    return None


def is_legit(scholarship):
    url = get_more_info_url(scholarship)
    if not url:
        return False
    res = verify_scholarship_url(url)
    val = res.get("is_legit")
    if isinstance(val, bool):
        return val
    if isinstance(val, str):
        return val.strip().lower() == "true"
    return bool(val)


def has_more_info_url(scholarship):
    """
    Returns True if the scholarship has a valid 'For more information' URL and is verified legit.
    """
    return get_more_info_url(scholarship) is not None and is_legit(scholarship)


if __name__ == "__main__":
    file_path = "current_scholarships.json"
    with open(file_path, "r", encoding="utf-8") as f:
        scholarships = json.load(f)

    filtered_scholarships = [s for s in tqdm(scholarships, desc="Verifying scholarships") if has_more_info_url(s)]

    print(f"Total scholarships before: {len(scholarships)}")
    print(f"Scholarships with valid 'For more information' URL & verified legit: {len(filtered_scholarships)}")

    with open("filtered.json", "w", encoding="utf-8") as f:
        json.dump(filtered_scholarships, f, indent=4)

    print(f"Saved {len(filtered_scholarships)} scholarships to {file_path}.")


