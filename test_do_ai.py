"""Quick test to verify DigitalOcean GenAI API connection."""
import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

api_key = os.getenv("DO_AI_API_KEY")
base_url = os.getenv("DO_AI_BASE_URL")
model = os.getenv("DO_AI_MODEL")

print(f"Base URL : {base_url}")
print(f"Model    : {model}")
print(f"Key      : {api_key[:20]}...")
print()

client = OpenAI(api_key=api_key, base_url=base_url)

response = client.chat.completions.create(
    model=model,
    messages=[{"role": "user", "content": "Say 'AgentTrade connected!' and nothing else."}],
    max_tokens=20,
)

print("Response:", response.choices[0].message.content)
print("\nDO GenAI API is working!")
