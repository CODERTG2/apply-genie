import ollama
from dotenv import load_dotenv
import os
import json
from tqdm import tqdm
from datetime import datetime, date

load_dotenv()

my_info = os.environ["MY_INFO"]

with open("scholarships.json", "r", encoding="utf-8") as f:
    scholarships = json.load(f)

eligible = []

for s in tqdm(scholarships):
    today = date.today()
    try:
        dates = s["Deadline"].split(";")
        future = False
        for d in dates:
            if (datetime.strptime(d.strip().strip(". "), "%B %d").replace(year=today.year).date() >= today):
                future = True
            
        if not future:
            continue
    
    except Exception:
        continue

    prompt = f"""
            Based on the info of the applicant and the info about the scholarship return a json if the applicant is eligible or not.
            Example Outputs: 
            {{
                "eligibility" : true
            }}
            {{
                "eligibility" : false
            }}
            Applicant Info: {my_info}

            Scholarship Info:
                Name: {s.get("Title", "N/A")},
                Level of Study: {s.get("Level of Study", "N/A")},
                Purpose: {s.get("Purpose", "N/A")},
                Focus: {s.get("Focus", "N/A")},
                Qualifications: {s.get("Qualifications", "N/A")}
            """

    try:
        response = ollama.chat(
            model='llama3.1:latest',
            messages=[
                {'role': 'system', 'content': 'You are great at classifying an applicant as eligble or not eligbile for a scholarship.'},
                {'role': 'user', 'content': prompt}
            ]
        ).message.content
        response = json.loads(response)

        if response["eligibility"] != "false":
            eligible.append(s)

    except Exception as e:
        continue

with open("eligible.json", "w", encoding="utf-8") as f:
    json.dump(eligible, f, indent=4, ensure_ascii=False)




