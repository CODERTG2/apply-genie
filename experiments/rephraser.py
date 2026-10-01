'''
Legacy Experiment: rephraser.py (Root Version)

Purpose:
An experimental script to rewrite complex specific requirements into simple Yes/No questions.

Capabilities:
- Used a local LLM to convert a "description" into a direct question.
- Determined if answering "Yes" to the question meant the applicant was eligible.
- Formatted output as JSON.

What it lacked:
- Operated on a monolithic JSON file in a single pass.
- Lacked integration with the main state-driven pipeline.
- The logic was refined and integrated cleanly into `src/steps/rephraser.py`.
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
    for req in scholarship.get("SpecificRequirements", []):
        prompt = f"""
            Take the specific scholarship requirement and convert it into a direct Yes/No question for the applicant.
            Then, determine if answering "Yes" to this question means the applicant is ELIGIBLE.

            Requirement: "{req['description']}"
        """

        completion = client.chat.completions.create(
            model=model,
            temperature=0.0,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a strict JSON data extractor. Convert the scholarship requirement into a Yes/No question.\n"
                        "Output ONLY valid JSON in the following format:\n"
                        "{\n"
                        '  "question": "The Yes/No question here",\n'
                        '  "yes_is_eligible": true or false\n'
                        "}\n"
                        "Do not include markdown blocks, quotes, or preamble."
                    )
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        )
        
        try:
            response_data = json.loads(completion.choices[0].message.content.strip())
            req["question"] = response_data.get("question")
            req["yes_is_eligible"] = response_data.get("yes_is_eligible")
            # print(f"\nDesc: {req['description']}\nQ: {req['question']} (Yes is Eligible: {req['yes_is_eligible']})")
        except json.JSONDecodeError:
            print(f"\nFailed to parse JSON for requirement: {req['description']}\nRaw Output: {completion.choices[0].message.content.strip()}")
            req["question"] = f"Do you meet: {req['description']}?"
            req["yes_is_eligible"] = True

with open("dry_run_classifications.json", "w", encoding="utf-8") as f:
    json.dump(scholarships, f, ensure_ascii=False, indent=4)
