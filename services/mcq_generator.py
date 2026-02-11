import json
import logging
import hashlib
import os
from typing import List, Dict, Optional
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

# Configure Gemini
api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    logging.warning("GEMINI_API_KEY not found in .env. MCQ generation may fail.")

genai.configure(api_key=api_key)

# Simple in-memory cache: {hash_of_input: questions_list}
MCQ_CACHE = {}

def generate_mcq_test(job_description: str, num_questions: int = 10) -> List[Dict]:
    """
    Generate a list of MCQ questions based on the job description.
    Uses caching to return instantly for identical requests.
    """
    if not api_key:
         logging.error("Gemini API key is missing.")
         return _get_fallback_questions()

    # Create cache key
    cache_key = hashlib.md5(f"{job_description}_{num_questions}".encode()).hexdigest()
    
    if cache_key in MCQ_CACHE:
        logging.info("Returning cached MCQ questions")
        return MCQ_CACHE[cache_key]

    model = genai.GenerativeModel('models/gemini-flash-latest')

    prompt = f"""
    You are a technical recruiter creating a screening test.
    Create {num_questions} multiple-choice questions (MCQ) to test candidates on the key skills mentioned in the job description.
    
    JOB DESCRIPTION:
    {job_description[:3000]}
    
    The questions should be technical and specific to the role.
    
    Return ONLY a JSON ARRAY of objects. Each object must have:
    - "question": string
    - "options": array of 4 strings
    - "correct_answer": integer (0, 1, 2, or 3) representing the index of the correct option.
    
    Example:
    [
      {{
        "question": "Which Python library is efficient for data manipulation?",
        "options": ["Numpy", "Pandas", "Requests", "Flask"],
        "correct_answer": 1
      }}
    ]
    
    Output strictly valid JSON.
    """

    try:
        response = model.generate_content(prompt)
        text_response = response.text
        
        # Clean up response if it contains markdown code blocks
        if "```json" in text_response:
             text_response = text_response.replace("```json", "").replace("```", "")
        elif "```" in text_response:
             text_response = text_response.replace("```", "")
             
        questions = json.loads(text_response)
        
        # Validate structure
        valid_questions = []
        if isinstance(questions, list):
            for i, q in enumerate(questions):
                if all(k in q for k in ["question", "options", "correct_answer"]) and len(q["options"]) == 4:
                    q["id"] = i
                    valid_questions.append(q)
        
        if len(valid_questions) < num_questions:
            logging.warning(f"Generated {len(valid_questions)} valid questions, requested {num_questions}. Padding with fallback.")
            valid_questions.extend(_get_fallback_questions()[len(valid_questions):])
            
        final_questions = valid_questions[:num_questions]
        
        # Cache the result
        MCQ_CACHE[cache_key] = final_questions
        return final_questions
        
    except Exception as e:
        logging.error(f"Error generating/parsing MCQ with Gemini: {e}")
        return _get_fallback_questions()

def score_mcq_test(candidate_answers: Dict[int, int], questions: List[Dict]) -> Dict:
    """
    Score the MCQ test.
    
    Args:
        candidate_answers: Dict mapping question ID to selected option index.
        questions: List of question objects (including correct_answer).
        
    Returns:
        Dict with score details.
    """
    correct_count = 0
    total = len(questions)
    details = []
    
    for q in questions:
        q_id = q.get("id")
        # Ensure we handle string/int keys if coming from JSON
        selected = candidate_answers.get(str(q_id)) 
        if selected is None:
             selected = candidate_answers.get(q_id)

        is_correct = False
        if selected is not None and int(selected) == q["correct_answer"]:
            is_correct = True
            correct_count += 1
            
        details.append({
            "question_id": q_id,
            "selected": selected,
            "correct": q["correct_answer"],
            "is_correct": is_correct
        })
        
    score_percent = (correct_count / total) * 100 if total > 0 else 0
    
    return {
        "score_percent": round(score_percent, 2),
        "correct_count": correct_count,
        "total_questions": total,
        "details": details
    }

def _get_fallback_questions() -> List[Dict]:
    """Fallback questions in case of generation failure."""
    return [
        {
            "id": 0,
            "question": "What does API stand for?",
            "options": ["Application Programming Interface", "Advanced Python Integration", "Automated Process Interaction", "Applied Protocol Interface"],
            "correct_answer": 0
        },
        {
            "id": 1,
            "question": "Which of these is a version control system?",
            "options": ["JIRA", "Git", "Slack", "Trello"],
            "correct_answer": 1
        },
        {
             "id": 2,
            "question": "What is the primary function of SQL?",
            "options": ["Styling Web Pages", "Managing Databases", "Compiling Code", "Sending Emails"],
            "correct_answer": 1
        },
        {
            "id": 3,
            "question": "Which HTTP method is typically used to retrieve data?",
            "options": ["POST", "PUT", "GET", "DELETE"],
            "correct_answer": 2
        },
         {
            "id": 4,
            "question": "What is a 'Bug' in software development?",
            "options": ["A feature", "An error or flaw", "A type of virus", "A fast processor"],
            "correct_answer": 1
        }
    ]
