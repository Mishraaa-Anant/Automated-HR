"""
Resume processing service with batch optimization.
Handles resume embeddings, caching, and candidate shortlisting.
"""

import os
import pickle
from pathlib import Path
from typing import Dict, List, Callable, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

import torch
import pandas as pd
from sentence_transformers import SentenceTransformer, util


from config import RESUME_FOLDER, EMBEDDING_CACHE, MAX_WORKERS
from utils.pdf_utils import extract_text_from_pdf


# Global cache for the model
_model_cache = None

def load_model():
    """Load and cache the sentence transformer model."""
    global _model_cache
    if _model_cache is None:
        # Upgraded to all-mpnet-base-v2 for better accuracy (slower but worth it)
        _model_cache = SentenceTransformer('all-mpnet-base-v2')
    return _model_cache


def load_embeddings_cache() -> Dict:
    """
    Load embeddings cache from disk.
    
    Returns:
        Dictionary of cached embeddings
    """
    if os.path.exists(EMBEDDING_CACHE):
        try:
            with open(EMBEDDING_CACHE, "rb") as f:
                return pickle.load(f)
        except Exception:
            return {}
    return {}


def save_embeddings_cache(cache: Dict):
    """
    Save embeddings cache to disk.
    
    Args:
        cache: Dictionary of embeddings to save
    """
    with open(EMBEDDING_CACHE, "wb") as f:
        pickle.dump(cache, f)


def ensure_embeddings_for_resumes(
    progress_callback: Optional[Callable[[int, int, str], None]] = None
) -> Dict:
    """
    Generate/update embeddings for all resumes with parallel processing.
    
    Args:
        progress_callback: Optional callback function(current, total, filename)
        
    Returns:
        Dictionary of embeddings and resume texts
    """
    model = load_model()
    model_dim = model.get_sentence_embedding_dimension()
    cache = load_embeddings_cache()
    
    # Validate cache
    regenerate = False
    for k, v in cache.items():
        e = v.get("embedding")
        if not isinstance(e, torch.Tensor) or e.shape[0] != model_dim:
            regenerate = True
            break
    
    if regenerate:
        cache = {}
    
    # Get list of PDFs to process
    pdf_files = [
        f for f in sorted(os.listdir(RESUME_FOLDER))
        if f.lower().endswith(".pdf") and f not in cache
    ]
    
    if not pdf_files:
        return cache
    
    # Process PDFs sequentially to avoid Streamlit session context issues
    changed = False
    total_files = len(pdf_files)
    
    for index, filename in enumerate(pdf_files):
        path = os.path.join(RESUME_FOLDER, filename)
        try:
            if progress_callback:
                progress_callback(index + 1, total_files, filename)
            
            text = extract_text_from_pdf(path)
            if text.strip():
                emb = model.encode(text, convert_to_tensor=True).cpu()
                cache[filename] = {"embedding": emb, "text": text}
                changed = True
        except Exception as e:
            if progress_callback:
                progress_callback(index + 1, total_files, f"{filename} (error)")
    
    if changed:
        save_embeddings_cache(cache)
    
    return cache


def advanced_shortlist(job_desc: str, top_k: int = None) -> pd.DataFrame:
    """
    Shortlist candidates based on semantic similarity.
    
    Args:
        job_desc: Job description text
        top_k: Number of top candidates to return (None = all resumes)
        
    Returns:
        DataFrame with filename, similarity, and text columns
    """
    model = load_model()
    cache = ensure_embeddings_for_resumes()
    jd_emb = model.encode(job_desc, convert_to_tensor=True).cpu()
    
    rows = []
    for fname, v in cache.items():
        sim = float(util.cos_sim(jd_emb, v["embedding"]).item())
        rows.append({
            "filename": fname,
            "similarity": sim,
            "text": v["text"]
        })
    
    df = pd.DataFrame(rows).sort_values("similarity", ascending=False)
    
    # If top_k is specified, limit results; otherwise return all
    if top_k:
        df = df.head(top_k)
    
    return df


def batch_process_resumes(
    job_desc: str,
    top_k: Optional[int],
    min_ats_score: int,
    ats_scorer: Callable,
    contact_extractor: Callable,
    progress_callback: Optional[Callable[[int, int, str], None]] = None,
    use_fast_scoring: bool = True  # NEW: Use fast scoring by default
) -> List[Dict]:
    """
    Batch process resumes with parallel ATS scoring and contact extraction.
    
    Args:
        job_desc: Job description
        top_k: Number of resumes to analyze (None = all resumes)
        min_ats_score: Minimum ATS score threshold
        ats_scorer: Function to calculate ATS scores (LLM-based, slow)
        contact_extractor: Function to extract contact info
        progress_callback: Optional progress callback
        use_fast_scoring: If True, use fast keyword-based scoring (10x faster)
        
    Returns:
        List of candidate dictionaries
    """
    from services.fast_ats_scoring import calculate_fast_ats_score
    
    # Get shortlisted resumes
    df = advanced_shortlist(job_desc, top_k)
    
    if df.empty:
        return []
    
    candidates = []
    total = len(df)
    processed_count = [0]  # Use list to make it mutable in nested function
    
    def process_candidate(row_data: tuple) -> Optional[Dict]:
        """Process a single candidate (thread-safe, no Streamlit calls)."""
        idx, row = row_data
        
        # Extract contact info (uses cache, minimal LLM)
        contact_info = contact_extractor(row['text'], row['filename'])
        
        # Calculate ATS score
        if use_fast_scoring:
            # Fast keyword-based scoring (no LLM, instant, with caching)
            ats_data = calculate_fast_ats_score(
                row['text'],
                job_desc,
                row['similarity'],
                row['filename'],  # Pass filename for caching
                None  # Load cache from disk
            )
        else:
            # Slow LLM-based scoring (uses cache if available)
            ats_data = ats_scorer(row['text'], job_desc, row['filename'])
        
        # Only include if meets threshold
        if ats_data['ats_score'] >= min_ats_score:
            return {
                "filename": row["filename"],
                "name": contact_info['name'],
                "email": contact_info['email'] or "",
                "phone": contact_info['phone'] or "",
                "linkedin": contact_info['linkedin'] or "",
                "similarity": round(float(row["similarity"]), 4),
                "ats_score": ats_data['ats_score'],
                "overall_grade": ats_data['overall_grade'],
                "keyword_match": ats_data['keyword_match_score'],
                "skills_match": ats_data['skills_match_score'],
                "experience_score": ats_data['experience_score'],
                "education_score": ats_data['education_score'],
                "hire_recommendation": ats_data['hire_recommendation'],
                "confidence": ats_data['confidence_level'],
                "ats_details": ats_data,
                "resume_text": row['text'],
                "meeting_link": "",
                "email_sent": False,
                "email_status": "pending"
            }
        return None
    
    # Process candidates in parallel (LLM calls are thread-safe)
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {
            executor.submit(process_candidate, row_data): (idx, row_data[1]['filename'])
            for idx, row_data in enumerate(df.iterrows())
        }
        
        for future in as_completed(futures):
            idx, filename = futures[future]
            processed_count[0] += 1
            
            # Call progress callback from main thread
            if progress_callback:
                progress_callback(processed_count[0], total, filename)
            
            result = future.result()
            if result:
                candidates.append(result)
    
    # Sort by ATS score
    candidates = sorted(candidates, key=lambda x: x['ats_score'], reverse=True)
    
    return candidates
