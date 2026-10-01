"""
Step 2: Filter scholarships — verify each has a legit URL.

Merged from src/filter.py + src/llmverifier.py.
Each scholarship is checked for a valid 'For more information' URL,
then the URL is fetched and an LLM verifies it's a real scholarship page.
"""

import re
import json
import requests
from openai import OpenAI
from core.config import LM_STUDIO_BASE_URL, FILTER_MODEL, LM_STUDIO_API_KEY


# ── URL verification via local LLM ──────────────────────────────

def _fetch_page_text(url: str, timeout: int = 10, max_chars: int = 8000) -> str:
    """Fetch HTML from a URL and extract clean readable text."""
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
    }
    response = requests.get(url, headers=headers, timeout=timeout)
    response.raise_for_status()

    html = response.text
    clean_html = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", html, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", clean_html)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:max_chars]


def _verify_scholarship_url(url: str) -> dict:
    """Use a local LLM to check if a URL is a legit scholarship page."""
    try:
        page_text = _fetch_page_text(url)
    except Exception as e:
        return {
            "url": url,
            "is_legit": False,
            "has_scholarship_info": False,
            "has_apply_method": False,
            "error": f"Failed to fetch URL content: {str(e)}",
            "reason": f"HTTP/Fetch error: {str(e)}"
        }

    client = OpenAI(base_url=LM_STUDIO_BASE_URL, api_key=LM_STUDIO_API_KEY)

    prompt = f"""Analyze the following webpage content from URL: {url}

Determine if this webpage is a legitimate scholarship page.
Check for:
1. Scholarship information (e.g. eligibility, qualifications, criteria, description, or award details).
2. Ability to apply or clear instructions on how to apply (e.g. application form, apply button, submission email/link).

Return ONLY valid JSON matching this exact structure:
{{
  "is_legit": true,
  "has_scholarship_info": true,
  "has_apply_method": true,
  "reason": "Brief explanation of your findings."
}}

WEBPAGE CONTENT:
{page_text}
"""

    try:
        response = client.chat.completions.create(
            model=FILTER_MODEL,
            messages=[
                {"role": "system", "content": "You are a web page verification agent. Return ONLY valid JSON."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,
        )

        content = response.choices[0].message.content.strip()
        if content.startswith("```"):
            content = re.sub(r"^```(?:json)?\n?", "", content)
            content = re.sub(r"\n?```$", "", content)

        parsed = json.loads(content)
        parsed["url"] = url
        return parsed

    except json.JSONDecodeError:
        return {
            "url": url,
            "is_legit": False,
            "has_scholarship_info": False,
            "has_apply_method": False,
            "reason": "Model output could not be parsed as JSON.",
            "raw_output": content if 'content' in locals() else None
        }
    except Exception as e:
        return {
            "url": url,
            "is_legit": False,
            "has_scholarship_info": False,
            "has_apply_method": False,
            "reason": f"LM Studio API call failed: {str(e)}"
        }


# ── Public API ───────────────────────────────────────────────────

def get_more_info_url(scholarship: dict) -> str | None:
    """Extract the URL from the 'For more information' field.
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


def filter_scholarship(scholarship: dict) -> bool:
    """Return True if the scholarship has a valid, verified URL.
    This is the single-item function called by the pipeline.
    """
    url = get_more_info_url(scholarship)
    if not url:
        return False

    res = _verify_scholarship_url(url)
    val = res.get("is_legit")
    if isinstance(val, bool):
        return val
    if isinstance(val, str):
        return val.strip().lower() == "true"
    return bool(val)


def filter_batch(scholarships: list) -> list:
    """Filter a list of scholarships, keeping only those with legit URLs.
    Returns the filtered list.
    """
    from tqdm import tqdm
    return [s for s in tqdm(scholarships, desc="Filtering scholarships") if filter_scholarship(s)]
