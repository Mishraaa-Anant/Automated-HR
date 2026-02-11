import logging
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from services.mcq_generator import generate_mcq_test
from dotenv import load_dotenv

# Configure logging to stdout
logging.basicConfig(level=logging.ERROR, stream=sys.stdout)

# Load env in case it's not loaded
load_dotenv()

print(f"Testing Gemini integration...")
api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    print("ERROR: GEMINI_API_KEY not found in env!")
    exit(1)
else:
    print(f"API Key loaded (first 5 chars): {api_key[:5]}...")

description = "We are looking for a Senior Python Developer with experience in FastAPI, Docker, and Kubernetes. The candidate should be proficient in asynchronous programming and microservices architecture."

print(f"Generating questions for JD: {description[:50]}...")
questions = generate_mcq_test(description, num_questions=3)

print(f"\nGenerated {len(questions)} questions:")
for q in questions:
    print(f"\n[Q] {q['question']}")
    print(f"    Options: {q['options']}")
    print(f"    Correct: {q['correct_answer']}")

if len(questions) == 3:
    print("\nSUCCESS: Generated required number of questions.")
else:
    print(f"\nWARNING: Generated {len(questions)} questions instead of 3. Fallback used.")
