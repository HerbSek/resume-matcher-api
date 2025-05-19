from groq import Groq
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize Groq client with minimal parameters
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

# Test a simple completion
try:
    response = client.chat.completions.create(
        messages=[{"role": "user", "content": "Hello, world!"}],
        model="llama-3.1-8b-instant"
    )
    print("Success!")
    print(response.choices[0].message.content)
except Exception as e:
    print(f"Error: {e}")