"""
Step 4: Extract exact dates from textual deadlines using a local LLM.
"""

from openai import OpenAI
from core.config import CURRENT_YEAR, DATE_MODEL

def extract_deadline(scholarship: dict, client: OpenAI) -> str | None:
    """Extract the specific deadline date from textual description."""
    
    # If already processed, skip
    if "Deadline_Date" in scholarship:
        return scholarship["Deadline_Date"]
        
    prompt = f"""
        Extract the deadline from the scholarship. Return ONLY the date. Structure it as the month date, year.
        
        Current year: {CURRENT_YEAR}
        If the scholarship does not have a year, assume it is for the current year. If the scholarship
        has a month but no year, assume the year is the current year.
        
        Example:
        January 1, {CURRENT_YEAR}
        September 2, 2024
        
        Scholarship info:
    """
    ctx = ""
    if "Deadline" in scholarship:
        ctx += "\nDeadline: " + str(scholarship["Deadline"])
    if "Month" in scholarship:
        ctx += "\nMonth: " + str(scholarship["Month"])
    if "Duration" in scholarship:
        ctx += "\nDuration: " + str(scholarship["Duration"])

    if not ctx:
        return None

    try:
        completion = client.chat.completions.create(
            model=DATE_MODEL,
            messages=[
                {"role": "user", "content": prompt + ctx}
            ],
            temperature=0.0
        )
        date = completion.choices[0].message.content.strip()
        scholarship["Deadline_Date"] = date
        return date
    except Exception as e:
        print(f"Failed to extract date for '{scholarship.get('Title')}': {e}")
        return None

def process_batch(scholarships: list, client: OpenAI) -> list:
    """Process a batch of scholarships."""
    from tqdm import tqdm
    for scholarship in tqdm(scholarships, desc="Extracting dates"):
        extract_deadline(scholarship, client)
    return scholarships
