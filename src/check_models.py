import os
from google import genai

# Grab the first API key from your environment variable
keys_env = os.environ.get("GEMINI_API_KEYS")
api_key = keys_env.split(",")[0].strip()

client = genai.Client(api_key=api_key)

print("Fetching available models...")
print("-" * 40)

# List all models available to your key that support content generation
available_models = []
for model in client.models.list():
    if "generateContent" in model.supported_actions:
        available_models.append(model.name)
        print(model.name)

print("-" * 40)
print(f"Total generateContent models found: {len(available_models)}")