import os
from dotenv import load_dotenv
from google import genai

load_dotenv()

client = genai.Client(api_key=os.getenv("GEMINI"))

response = client.models.generate_content(
    model="gemini-3.5-flash-lite",
    contents="Explain how AI works in a few words.",
)

print(response.text)
