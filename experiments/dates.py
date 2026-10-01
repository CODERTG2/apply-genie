'''
Legacy Experiment: dates.py (Root Version)

Purpose:
An early script to extract deadline dates using a local LLM (meta-llama-3.1-8b-instruct) via LM Studio.

Capabilities:
- Read a monolithic JSON file of scholarships.
- Used a basic prompt to extract just the Date string, assuming the current year if missing.

What it lacked:
- Modified a massive JSON file directly rather than operating on a stream or pipeline of individual items.
- Lacked robust error handling.
- The core logic was eventually refactored and moved into `src/steps/dates.py`.
'''
from openai import OpenAI
import json
from tqdm import tqdm

YEAR = 2026

model = "meta-llama-3.1-8b-instruct"

client = OpenAI(
    base_url="http://localhost:1234/v1", 
    api_key="lm-studio"
)

with open("dry_run_classifications.json", "r", encoding="utf-8") as f:
    scholarships = json.load(f)

for scholarship in tqdm(scholarships):
    prompt = f"""
        Extract the deadline from the scholarship. Return ONLY the date. Structure it as the month date, year.
        
        Current year: {YEAR}
        If the scholarship does not have a year, assume it is for the current year. If the scholarship
        has a month but no year, assume the year is the current year.
        
        Example:
        January 1, 2026
        September 2, 2024
        
        Scholarship info:
    """
    ctx = ""
    if "Deadline_Date" in scholarship.keys():
        continue
    if "Deadline" in scholarship.keys():
        ctx += "\nDeadline: " + scholarship["Deadline"]
    if "Month" in scholarship.keys():
        ctx += "\nMonth: " + scholarship["Month"]
    if "Duration" in scholarship.keys():
        ctx += "\nDuration: " + scholarship["Duration"]

    completion = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "user", "content": prompt + ctx}
        ])

    date = completion.choices[0].message.content
    scholarship["Deadline_Date"] = date

    with open("dry_run_classifications.json", "w", encoding="utf-8") as f:
        json.dump(scholarships, f, ensure_ascii=False, indent=4)
