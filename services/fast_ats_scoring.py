"""
Fast keyword-based ATS scoring (no LLM required).
Uses regex and keyword matching for instant scoring.
"""

import re
from typing import Dict, List, Set
from config import TECH_KEYWORDS


def extract_keywords_from_text(text: str) -> Set[str]:
    """Extract potential keywords from text."""
    # Convert to lowercase
    text_lower = text.lower()
    
    # Extract words (alphanumeric, 2+ chars)
    words = set(re.findall(r'\b[a-z0-9+#]{2,}\b', text_lower))
    
    # Extract common tech terms
    tech_terms = set()
    for keyword in TECH_KEYWORDS:
        if keyword in text_lower:
            tech_terms.add(keyword)
    
    # Extract programming languages and frameworks
    patterns = [
        r'\b(python|java|javascript|typescript|c\+\+|c#|ruby|go|rust|swift|kotlin)\b',
        r'\b(react|angular|vue|django|flask|spring|express|fastapi)\b',
        r'\b(sql|mysql|postgresql|mongodb|redis|elasticsearch)\b',
        r'\b(aws|azure|gcp|docker|kubernetes|jenkins|terraform)\b',
        r'\b(git|github|gitlab|bitbucket|jira|confluence)\b',
    ]
    
    for pattern in patterns:
        matches = re.findall(pattern, text_lower)
        tech_terms.update(matches)
    
    return words.union(tech_terms)


def calculate_keyword_score(resume_keywords: Set[str], jd_keywords: Set[str]) -> int:
    """Calculate keyword match percentage."""
    if not jd_keywords:
        return 50
    
    matched = resume_keywords.intersection(jd_keywords)
    score = int((len(matched) / len(jd_keywords)) * 100)
    return min(100, score)


def calculate_fast_ats_score(
    resume_text: str,
    job_description: str,
    similarity_score: float = 0.0,
    filename: str = None,
    cache: dict = None
) -> Dict:
    """
    Ultra-fast ATS scoring using keyword matching (no LLM).
    Now with persistent caching support.
    
    Args:
        resume_text: Resume text
        job_description: Job description
        similarity_score: Semantic similarity score (0-1)
        filename: Optional filename for caching
        cache: Optional cache dictionary (if None, loads from disk)
        
    Returns:
        Dictionary with ATS scoring results
    """
    from utils.cache_utils import load_ats_cache, save_ats_cache
    
    # Load cache from disk if not provided
    if cache is None:
        cache = load_ats_cache()
        save_to_disk = True
    else:
        save_to_disk = False
    
    # Check cache (use "fast_" prefix to distinguish from LLM cache)
    if filename:
        cache_key = f"fast_{filename}_{hash(job_description)}"
        if cache_key in cache:
            return cache[cache_key]
    
    # Extract keywords
    resume_keywords = extract_keywords_from_text(resume_text)
    jd_keywords = extract_keywords_from_text(job_description)
    
    # Calculate keyword match
    keyword_score = calculate_keyword_score(resume_keywords, jd_keywords)
    
    # Find matched and missing keywords
    matched_keywords = list(resume_keywords.intersection(jd_keywords))[:10]
    missing_keywords = list(jd_keywords - resume_keywords)[:10]
    
    # Estimate experience (count years mentioned)
    years_pattern = r'(\d+)\+?\s*(?:years?|yrs?)'
    years_matches = re.findall(years_pattern, resume_text.lower())
    years_of_experience = max([int(y) for y in years_matches], default=0)
    
    # Detect education level
    education_level = "Unknown"
    text_lower = resume_text.lower()
    if any(term in text_lower for term in ['phd', 'ph.d', 'doctorate']):
        education_level = "PhD"
        education_score = 100
    elif any(term in text_lower for term in ['master', 'msc', 'm.sc', 'mba', 'm.b.a']):
        education_level = "Masters"
        education_score = 90
    elif any(term in text_lower for term in ['bachelor', 'bsc', 'b.sc', 'b.tech', 'b.e']):
        education_level = "Bachelors"
        education_score = 80
    else:
        education_score = 60
    
    # Calculate experience score
    if years_of_experience >= 5:
        experience_score = 90
    elif years_of_experience >= 3:
        experience_score = 80
    elif years_of_experience >= 1:
        experience_score = 70
    else:
        experience_score = 60
    
    # Use semantic similarity to boost scores
    # Similarity captures general meaning better than exact keywords
    similarity_percentage = int(similarity_score * 100)
    
    # Boost keyword score with similarity (if similarity is high, it compensates for missing keywords)
    if similarity_percentage > 70:
        keyword_score = max(keyword_score, (keyword_score + similarity_percentage) // 2)
    
    # Skills match is a blend of keywords and semantic meaning
    skills_match_score = min(100, (keyword_score + similarity_percentage) // 2)
    
    # If semantic match is very strong, ensure skills score reflects it
    if similarity_percentage > 80:
        skills_match_score = max(skills_match_score, similarity_percentage)
    
    # Calculate overall ATS score
    # Increased weight for skills/similarity (0.40) to be more "smart"
    ats_score = int(
        keyword_score * 0.30 +           # Reduced from 0.35
        skills_match_score * 0.40 +      # Increased from 0.30
        experience_score * 0.20 +        # Kept same
        education_score * 0.10           # Reduced from 0.15
    )
    
    # Intelligent Score Boosting
    # If semantic similarity is high, the candidate IS a good match regardless of exact keywords
    if similarity_percentage >= 85:
        ats_score = max(ats_score, 85)   # Guarantee "Strong Hire" range
    elif similarity_percentage >= 75:
        ats_score = max(ats_score, 75)   # Guarantee "Hire" range
    elif similarity_percentage >= 65:
        ats_score = max(ats_score, 65)   # Guarantee "Consider" range
    
    # Determine grade and recommendation
    if ats_score >= 85:
        overall_grade = "A"
        hire_recommendation = "Strong Hire"
        confidence = "High"
    elif ats_score >= 75:
        overall_grade = "B+"
        hire_recommendation = "Hire"
        confidence = "High"
    elif ats_score >= 65:
        overall_grade = "B"
        hire_recommendation = "Consider"
        confidence = "Medium"
    elif ats_score >= 55:
        overall_grade = "C+"
        hire_recommendation = "Maybe"
        confidence = "Medium"
    else:
        overall_grade = "C"
        hire_recommendation = "Weak Match"
        confidence = "Low"
    
    # Identify strengths
    key_strengths = []
    if keyword_score >= 70:
        key_strengths.append("Strong keyword match")
    if years_of_experience >= 5:
        key_strengths.append(f"{years_of_experience}+ years experience")
    if education_level in ["Masters", "PhD"]:
        key_strengths.append(f"{education_level} degree")
    if similarity_percentage >= 75:
        key_strengths.append(f"High semantic match ({similarity_percentage}%)")
    
    if not key_strengths:
        key_strengths = ["Resume parsed successfully"]
    
    # Identify red flags
    red_flags = []
    if keyword_score < 40:
        red_flags.append("Low keyword match")
    if years_of_experience == 0:
        red_flags.append("No clear experience mentioned")
    
    result = {
        "ats_score": ats_score,
        "keyword_match_score": keyword_score,
        "skills_match_score": skills_match_score,
        "experience_score": experience_score,
        "education_score": education_score,
        "overall_grade": overall_grade,
        "matched_keywords": matched_keywords,
        "missing_keywords": missing_keywords,
        "matched_skills": matched_keywords[:5],
        "missing_skills": missing_keywords[:5],
        "years_of_experience": years_of_experience,
        "education_level": education_level,
        "key_strengths": key_strengths,
        "red_flags": red_flags,
        "hire_recommendation": hire_recommendation,
        "confidence_level": confidence,
        "detailed_notes": f"Fast keyword-based scoring. Matched {len(matched_keywords)} keywords. {hire_recommendation}.",
        "scoring_method": "fast_keyword"  # Indicator that this is fast scoring
    }
    
    # Cache result to disk
    if filename:
        cache_key = f"fast_{filename}_{hash(job_description)}"
        cache[cache_key] = result
        if save_to_disk:
            save_ats_cache(cache)
    
    return result
