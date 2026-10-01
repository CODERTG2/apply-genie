"""
Step 5: Rephrase specific requirements into Yes/No questions.
Uses local LLM.
"""

import json
from openai import OpenAI
from core.config import REPHRASER_MODEL

def rephrase_requirements(scholarship: dict, client: OpenAI) -> dict:
    """Iterate through SpecificRequirements and generate Yes/No questions."""
    
    reqs = scholarship.get("SpecificRequirements", [])
    if not reqs:
        return scholarship
        
    for req in reqs:
        # Check if already processed (crash recovery)
        if "question" in req:
            continue
            
        prompt = f"""
            Take the specific scholarship requirement and convert it into a direct Yes/No question for the applicant.
            Then, determine if answering "Yes" to this question means the applicant is ELIGIBLE.

            Requirement: "{req['description']}"
        """

        try:
            completion = client.chat.completions.create(
                model=REPHRASER_MODEL,
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
            
            response_data = json.loads(completion.choices[0].message.content.strip())
            req["question"] = response_data.get("question")
            req["yes_is_eligible"] = response_data.get("yes_is_eligible")
            
        except (json.JSONDecodeError, Exception) as e:
            # Fallback
            req["question"] = f"Do you meet: {req['description']}?"
            req["yes_is_eligible"] = True

    return scholarship

def process_batch(scholarships: list, client: OpenAI) -> list:
    """Process a batch of scholarships."""
    from tqdm import tqdm
    for scholarship in tqdm(scholarships, desc="Rephrasing requirements"):
        rephrase_requirements(scholarship, client)
    return scholarships
