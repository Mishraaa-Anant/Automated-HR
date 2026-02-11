"""
Contact information extraction utilities.
Extracts emails, phone numbers, names, and LinkedIn profiles from resume text.
"""

import re
from typing import Dict, List, Optional
from config import EMAIL_PATTERNS, PHONE_PATTERNS
from utils.ollama_client import call_ollama


def extract_emails_advanced(text: str) -> List[str]:
    """
    Extract email addresses using multiple regex patterns and validation.
    
    Args:
        text: Resume text to extract emails from
        
    Returns:
        List of validated email addresses
    """
    emails = set()
    
    # Try all patterns
    for pattern in EMAIL_PATTERNS:
        matches = re.findall(pattern, text, re.IGNORECASE)
        for match in matches:
            if isinstance(match, tuple):
                match = match[0]
            email = match.strip().lower()
            
            # Validate email
            if '@' in email and '.' in email.split('@')[-1]:
                # Remove common false positives
                if not any(x in email for x in ['example.com', 'domain.com', 'email.com', 'test.com']):
                    emails.add(email)
    
    # Sort by common email providers first
    return sorted(list(emails), key=lambda x: (
        '@gmail.com' not in x,
        '@outlook.com' not in x,
        '@yahoo.com' not in x,
        len(x)
    ))


def extract_phones_advanced(text: str) -> List[str]:
    """
    Extract phone numbers using multiple regex patterns.
    
    Args:
        text: Resume text to extract phone numbers from
        
    Returns:
        List of phone numbers
    """
    phones = set()
    
    for pattern in PHONE_PATTERNS:
        matches = re.findall(pattern, text)
        for match in matches:
            if isinstance(match, tuple):
                match = match[0]
            phone = re.sub(r'[^\d+]', '', match.strip())
            if 10 <= len(phone) <= 15:
                phones.add(match.strip())
    
    return list(phones)


def extract_name_advanced(text: str) -> str:
    """
    Extract candidate name intelligently from resume.
    
    Args:
        text: Resume text to extract name from
        
    Returns:
        Candidate name
    """
    lines = [l.strip() for l in text.split('\n') if l.strip()]
    
    # Skip common headers
    skip_words = ['resume', 'cv', 'curriculum vitae', 'profile', 'contact', 'email', 'phone']
    
    for line in lines[:10]:
        line_lower = line.lower()
        
        # Skip if contains email or phone
        if '@' in line or re.search(r'\d{10}', line):
            continue
            
        # Skip common headers
        if any(word in line_lower for word in skip_words):
            continue
            
        # Check if looks like a name (2-4 words, mostly letters)
        words = line.split()
        if 2 <= len(words) <= 4:
            if all(len(w) > 1 and w[0].isupper() for w in words):
                return line[:50]
    
    return lines[0][:50] if lines else "Unknown"


def extract_contact_info_hybrid(
    resume_text: str,
    filename: Optional[str] = None,
    cache: Optional[Dict] = None
) -> Dict[str, Optional[str]]:
    """
    Hybrid approach: Regex first, then LLM fallback for missing info.
    Uses persistent disk cache to avoid re-extraction.
    
    Args:
        resume_text: Full resume text
        filename: Optional filename for caching
        cache: Optional cache dictionary (if None, loads from disk)
        
    Returns:
        Dictionary with name, email, phone, linkedin
    """
    from utils.cache_utils import load_contact_cache, save_contact_cache
    
    # Load cache from disk if not provided
    if cache is None:
        cache = load_contact_cache()
        save_to_disk = True
    else:
        save_to_disk = False
    
    # Check cache
    if filename and filename in cache:
        return cache[filename]
    
    # Step 1: Regex extraction
    emails = extract_emails_advanced(resume_text)
    phones = extract_phones_advanced(resume_text)
    name = extract_name_advanced(resume_text)
    
    # Step 2: LLM fallback ONLY if regex completely failed
    # This dramatically reduces LLM calls
    if not emails and not phones:
        # Only call LLM if we're missing both email AND phone
        llm_prompt = f"""Extract email and phone from this resume. Return in format:
Email: <email or NONE>
Phone: <phone or NONE>

Resume (first 1500 chars):
{resume_text[:1500]}

Response:"""
        
        response = call_ollama(llm_prompt, temperature=0.1).strip()
        
        # Try to extract from response
        llm_emails = extract_emails_advanced(response)
        llm_phones = extract_phones_advanced(response)
        
        if llm_emails:
            emails = llm_emails
        if llm_phones:
            phones = llm_phones
    elif not emails:
        # Quick LLM call just for email
        llm_prompt = f"""Extract ONLY the email from this resume:
{resume_text[:1000]}

Email:"""
        response = call_ollama(llm_prompt, temperature=0.1).strip()
        llm_emails = extract_emails_advanced(response)
        if llm_emails:
            emails = llm_emails
    elif not phones:
        # Quick LLM call just for phone
        llm_prompt = f"""Extract ONLY the phone number from this resume:
{resume_text[:1000]}

Phone:"""
        response = call_ollama(llm_prompt, temperature=0.1).strip()
        llm_phones = extract_phones_advanced(response)
        if llm_phones:
            phones = llm_phones
    
    # Extract LinkedIn
    linkedin = None
    linkedin_match = re.search(r'linkedin\.com/in/([a-zA-Z0-9\-]+)', resume_text, re.IGNORECASE)
    if linkedin_match:
        linkedin = f"linkedin.com/in/{linkedin_match.group(1)}"
    
    result = {
        "name": name,
        "email": emails[0] if emails else None,
        "phone": phones[0] if phones else None,
        "linkedin": linkedin
    }
    
    # Cache result
    if filename:
        cache[filename] = result
        if save_to_disk:
            save_contact_cache(cache)
    
    return result
