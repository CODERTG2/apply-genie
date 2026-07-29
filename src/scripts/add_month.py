import json

MONTH = "August"

with open("current_scholarships.json", 'r', encoding='utf-8') as f:
    scholarships = json.load(f)

for scholarship in scholarships:
    scholarship["Month"] = MONTH

with open("current_scholarships.json", "w", encoding="utf-8") as f:
    json.dump(scholarships, f, ensure_ascii=False, indent=4)