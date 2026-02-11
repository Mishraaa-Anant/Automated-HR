"""
Ollama API client for LLM interactions.
"""

import requests
from typing import Optional
from config import OLLAMA_API_URL, OLLAMA_MODEL


def call_ollama(
    prompt: str,
    system_prompt: Optional[str] = None,
    temperature: float = 0.3,
    max_retries: int = 2
) -> str:
    """
    Call Ollama API with retry logic.
    
    Args:
        prompt: The prompt to send to the LLM
        system_prompt: Optional system prompt for context
        temperature: Temperature for response randomness (0.0-1.0)
        max_retries: Number of retry attempts on failure
        
    Returns:
        LLM response as string
    """
    for attempt in range(max_retries):
        try:
            url = f"{OLLAMA_API_URL}/api/generate"
            payload = {
                "model": OLLAMA_MODEL,
                "prompt": prompt,
                "stream": False,
                "temperature": temperature,
                "num_predict": 1000
            }
            
            if system_prompt:
                payload["system"] = system_prompt
            
            response = requests.post(url, json=payload, timeout=120)
            
            if response.status_code == 200:
                return response.json().get("response", "")
            else:
                if attempt < max_retries - 1:
                    continue
                return f"Error: Status {response.status_code}"
                
        except Exception as e:
            if attempt < max_retries - 1:
                continue
            return f"Error: {str(e)}"
    
    return ""


def check_ollama_status() -> tuple[bool, str]:
    """
    Check if Ollama server is running and accessible.
    
    Returns:
        Tuple of (is_running, status_message)
    """
    try:
        response = requests.get(f"{OLLAMA_API_URL}/api/tags", timeout=5)
        if response.status_code == 200:
            return True, f"Connected - Model: {OLLAMA_MODEL}"
        else:
            return False, f"Connection Error: Status {response.status_code}"
    except Exception as e:
        return False, f"Ollama Not Running: {str(e)}"
