"""
ATS (Applicant Tracking System) scoring service.
Evaluates resumes against job descriptions using LLM-based analysis.
"""

import json
import re
from typing import Dict, List, Optional
from utils.ollama_client import call_ollama
from config import TECH_KEYWORDS


def extract_key_terms(text: str, max_terms: int = 20) -> List[str]:
    """
    Extract key technical terms and skills from job description.
    
    Args:
        text: Job description text
        max_terms: Maximum number of terms to extract
        
    Returns:
        List of key terms/skills
    """
    text_lower = text.lower()
    found = []
    
    # Find tech keywords
    for keyword in TECH_KEYWORDS:
        if keyword in text_lower:
            found.append(keyword)
    
    # Extract multi-word terms
    words = re.findall(r'\b[a-z]{3,}\b', text_lower)
    word_freq = {}
    
    # Skip common words
    skip_words = {'the', 'and', 'for', 'with', 'this', 'that', 'from', 'have', 'will', 'are', 'was'}
    
    for word in words:
        if word not in skip_words:
            word_freq[word] = word_freq.get(word, 0) + 1
    
    # Get top frequent words
    top_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)[:max_terms]
    found.extend([w[0] for w in top_words if w[0] not in found])
    
    return found[:max_terms]


def calculate_ats_score_enhanced(
    resume_text: str,
    job_description: str,
    filename: Optional[str] = None,
    cache: Optional[Dict] = None
) -> Dict:
    """
    Advanced ATS scoring with improved prompt engineering.
    Uses persistent disk cache to avoid re-analysis.
    
    Args:
        resume_text: Full resume text
        job_description: Job description text
        filename: Optional filename for caching
        cache: Optional cache dictionary (if None, loads from disk)
        
    Returns:
        Dictionary with detailed ATS scoring results
    """
    from utils.cache_utils import load_ats_cache, save_ats_cache
    
    # Load cache from disk if not provided
    if cache is None:
        cache = load_ats_cache()
        save_to_disk = True
    else:
        save_to_disk = False
    
    # Check cache
    if filename:
        cache_key = f"{filename}_{hash(job_description)}"
        if cache_key in cache:
            return cache[cache_key]
    
    system_prompt = """You are an expert ATS (Applicant Tracking System) analyzer. 
Your job is to evaluate resumes against job descriptions with high precision.
Focus on: keyword matching, skills alignment, experience relevance, education fit.
Be objective, thorough, and strict in your evaluation."""
    
    # Extract key requirements from JD
    jd_keywords = extract_key_terms(job_description)
    
    prompt = f"""Analyze resume vs job requirements. Return ONLY valid JSON.

JOB (key requirements): {', '.join(jd_keywords[:12])}

RESUME (first 2500 chars):
{resume_text[:2500]}

Return JSON ONLY:
{{
    "ats_score": 85,
    "keyword_match_score": 80,
    "skills_match_score": 85,
    "experience_score": 90,
    "education_score": 80,
    "overall_grade": "A",
    "matched_keywords": ["python", "sql"],
    "missing_keywords": ["docker"],
    "matched_skills": ["data analysis"],
    "missing_skills": ["cloud"],
    "years_of_experience": 5,
    "education_level": "Masters",
    "key_strengths": ["Strong tech skills"],
    "red_flags": [],
    "hire_recommendation": "Strong Hire",
    "confidence_level": "High",
    "detailed_notes": "Excellent match"
}}

Rules: 85+=Strong Hire, 70-84=Hire, 60-69=Maybe, <60=Reject. Be strict.

JSON:"""
    
    response = call_ollama(prompt, system_prompt, temperature=0.2)
    
    # Parse JSON with error handling
    try:
        # Extract JSON
        json_start = response.find('{')
        json_end = response.rfind('}') + 1
        
        if json_start == -1 or json_end <= json_start:
            raise ValueError("No JSON found in response")
        
        json_str = response[json_start:json_end]
        
        # Clean JSON
        json_str = json_str.replace('\n', ' ').replace('\r', ' ').replace('\t', ' ')
        json_str = ' '.join(json_str.split())
        
        result = json.loads(json_str)
        
        # Validate required fields
        required = ['ats_score', 'keyword_match_score', 'skills_match_score',
                    'experience_score', 'education_score', 'overall_grade']
        
        if all(field in result for field in required):
            # Validate scores are integers
            for field in ['ats_score', 'keyword_match_score', 'skills_match_score',
                          'experience_score', 'education_score']:
                if not isinstance(result[field], (int, float)):
                    result[field] = 65
                result[field] = max(0, min(100, int(result[field])))
            
            # Cache result
            if filename:
                cache_key = f"{filename}_{hash(job_description)}"
                cache[cache_key] = result
                if save_to_disk:
                    save_ats_cache(cache)
            
            return result
        
    except Exception:
        pass
    
    # Enhanced fallback with keyword matching
    keywords_found = sum(1 for kw in jd_keywords if kw.lower() in resume_text.lower())
    keyword_score = min(100, int((keywords_found / max(len(jd_keywords), 1)) * 100))
    
    result = {
        "ats_score": max(50, keyword_score - 10),
        "keyword_match_score": keyword_score,
        "skills_match_score": 60,
        "experience_score": 65,
        "education_score": 60,
        "overall_grade": "C+",
        "matched_keywords": jd_keywords[:min(keywords_found, 5)],
        "missing_keywords": jd_keywords[keywords_found:keywords_found+5],
        "matched_skills": ["Analysis pending"],
        "missing_skills": ["Full analysis needed"],
        "years_of_experience": 0,
        "education_level": "Unknown",
        "key_strengths": ["Resume parsed successfully"],
        "red_flags": ["LLM analysis unavailable"],
        "hire_recommendation": "Review Required",
        "confidence_level": "Medium",
        "detailed_notes": "Fallback scoring used. Manual review recommended."
    }
    
    if filename:
        cache_key = f"{filename}_{hash(job_description)}"
        cache[cache_key] = result
        if save_to_disk:
            save_ats_cache(cache)
    
    return result
