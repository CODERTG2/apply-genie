'''
Legacy Experiment: llmverifier.py

Purpose:
A helper script used by the experimental `filter.py` to visit a webpage and use an LLM to verify if it's a real scholarship page.

Capabilities:
- Fetched raw HTML using the `requests` library.
- Stripped script/style tags and normalized whitespace.
- Prompted a local LLM to output a JSON verification object indicating legitimacy and presence of apply methods.

What it lacked:
- Scraping generic web pages using just `requests` is brittle; many sites block it.
- The HTML stripping was rudimentary.
- The entire approach of verifying every URL via an LLM on-the-fly proved too slow for production use.
'''
import os
import re
import json
import requests
from openai import OpenAI

# ==========================================
# CONFIGURATION
# ==========================================
URL = "https://www.regiafoundation.org/scholarship"
LM_STUDIO_BASE_URL = os.getenv("LM_STUDIO_BASE_URL", "http://localhost:1234/v1")
LM_STUDIO_MODEL = os.getenv("LM_STUDIO_MODEL", "google/gemma-4-e4b")


def fetch_page_text(url: str, timeout: int = 10, max_chars: int = 8000) -> str:
    """
    Fetches the HTML content of a URL and extracts clean readable text.
    """
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
    }
    response = requests.get(url, headers=headers, timeout=timeout)
    response.raise_for_status()

    html = response.text
    # Remove script and style elements
    clean_html = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", html, flags=re.DOTALL | re.IGNORECASE)
    # Strip HTML tags
    text = re.sub(r"<[^>]+>", " ", clean_html)
    # Normalize whitespace
    text = re.sub(r"\s+", " ", text).strip()
    return text[:max_chars]


def verify_scholarship_url(
    url: str,
    base_url: str = LM_STUDIO_BASE_URL,
    model: str = LM_STUDIO_MODEL,
    api_key: str = "lm-studio"
) -> dict:
    """
    Fetches HTML content from URL and queries an LM Studio local model (via OpenAI client)
    to check if the page contains legitimate scholarship info and application ability.
    """
    try:
        page_text = fetch_page_text(url)
    except Exception as e:
        return {
            "url": url,
            "is_legit": False,
            "has_scholarship_info": False,
            "has_apply_method": False,
            "error": f"Failed to fetch URL content: {str(e)}",
            "reason": f"HTTP/Fetch error: {str(e)}"
        }

    client = OpenAI(base_url=base_url, api_key=api_key)

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
            model=model,
            messages=[
                {"role": "system", "content": "You are a web page verification agent. Return ONLY valid JSON."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,
        )

        content = response.choices[0].message.content.strip()

        # Handle potential markdown code blocks in model output
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


if __name__ == "__main__":
    print(f"Testing URL verification for:\n  {URL}\n")
    print(f"Connecting to LM Studio at: {LM_STUDIO_BASE_URL} (Model: {LM_STUDIO_MODEL})\n")

    result = verify_scholarship_url(URL)
    print("Verification Result:")
    print(json.dumps(result, indent=2))
