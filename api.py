import json
import uuid
import logging
from typing import List, Optional, Dict

# ... (Previous imports remain same) ...
from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks, status
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import shutil
import os
import uvicorn
from contextlib import asynccontextmanager

# Configure Logging
logging.basicConfig(level=logging.INFO)

# Import Services
from config import RESUME_FOLDER
from utils.contact_extraction import extract_contact_info_hybrid
from services.ats_scoring import calculate_ats_score_enhanced
from services.resume_processor import batch_process_resumes, ensure_embeddings_for_resumes
from services.email_service import send_bulk_emails
from services.mcq_generator import generate_mcq_test, score_mcq_test

HISTORY_FILE = "data/history.json"

# Models
class AnalysisRequest(BaseModel):
    job_title: str
    job_description: str
    top_n: int = 10
    auto_email: bool = False

class CandidateResponse(BaseModel):
    id: str  # Added ID for persistence/deletion
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    ats_score: int
    overall_grade: str
    hire_recommendation: str
    is_shortlisted: bool = False
    meeting_link: Optional[str] = None
    email_status: str
    job_role: Optional[str] = None # To track which job they applied for
    # New Fields
    interview_time: Optional[str] = None
    mcq_score: Optional[float] = 0.0
    hr_score: Optional[float] = 0.0
    final_score: Optional[float] = 0.0
    test_status: str = "pending" # pending, completed
    test_data: Optional[List[Dict]] = None # Questions

# Persistence Helpers
def load_history() -> List[Dict]:
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r") as f:
                return json.load(f)
        except:
            return []
    return []

def save_history(data: List[Dict]):
    with open(HISTORY_FILE, "w") as f:
        json.dump(data, f, indent=2)

# Initialize App
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    os.makedirs(RESUME_FOLDER, exist_ok=True)
    # Load history into memory on startup if needed, or just read on demand
    global analysis_results
    analysis_results = load_history()
    yield
    # Shutdown

app = FastAPI(title="Jobs.AI API", version="3.1", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global State (synced with file)
analysis_results = []

# Routes
@app.post("/api/upload")
async def upload_resumes(files: List[UploadFile] = File(...)):
    """Upload PDF resumes to server"""
    count = 0
    for file in files:
        if file.filename.endswith(".pdf"):
            path = os.path.join(RESUME_FOLDER, file.filename)
            with open(path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
            count += 1
    return {"message": f"Successfully uploaded {count} resumes"}

@app.post("/api/analyze")
def analyze_candidates(request: AnalysisRequest, background_tasks: BackgroundTasks):
    """Trigger ATS analysis (Runs in threadpool to avoid blocking)"""
    global analysis_results
    
    # 1. Embeddings
    ensure_embeddings_for_resumes()
    
    # 2. Process
    logging.info("Starting batch processing...")
    new_candidates = batch_process_resumes(
        request.job_description,
        None,
        0,
        lambda text, jd, fname: calculate_ats_score_enhanced(text, jd, fname, None),
        lambda text, fname: extract_contact_info_hybrid(text, fname, None),
        use_fast_scoring=True
    )
    
    # 3. Post-Process & ID Generation
    processed_chunk = []
    
    # Generate MCQ Test for this batch (once per JD)
    batch_test_questions = generate_mcq_test(request.job_description)
    
    for c in new_candidates:
        c['id'] = str(uuid.uuid4())
        c['job_role'] = request.job_title
        c['test_data'] = batch_test_questions
        c['test_status'] = 'pending'
        c['mcq_score'] = 0.0
        c['hr_score'] = 0.0
        c['final_score'] = 0.0
        c['interview_time'] = None
        processed_chunk.append(c)

    # 4. Sort & Shortlist (Local chunk)
    processed_chunk = sorted(processed_chunk, key=lambda x: x['ats_score'], reverse=True)
    
    shortlisted_count = 0
    for c in processed_chunk:
        # Only shortlist if they have an email AND are within top N
        has_email = bool(c.get('email'))
        if has_email and shortlisted_count < request.top_n:
             c['is_shortlisted'] = True
             shortlisted_count += 1
        else:
             c['is_shortlisted'] = False

    # 5. Append to History & Save
    # We prepend so newest are first
    analysis_results = processed_chunk + analysis_results
    save_history(analysis_results)
    
    # 6. Auto Email (Background Task) - DEPRECATED in favor of manual scheduling
    # But keeping logic if user wants auto-send (will send without interview time)
    if request.auto_email:
        top_candidates = [c for c in processed_chunk if c['is_shortlisted']]
        background_tasks.add_task(
            send_bulk_emails_and_update, 
            top_candidates, 
            request.job_title
        )
        
    return {
        "message": "Analysis complete", 
        "total_candidates": len(processed_chunk),
        "shortlisted": shortlisted_count
    }

def send_bulk_emails_and_update(candidates, job_title):
    """Send emails and update history file with new status"""
    from services.email_service import send_bulk_emails
    
    # Inject test links if needed
    for c in candidates:
        if not c.get('test_link'):
             # Using localhost for demo. In prod, this would be the actual domain.
             c['test_link'] = f"http://localhost:8000/test.html?id={c['id']}"

    # Send
    results = send_bulk_emails(candidates, job_title)
    
    # Update persistent store
    global analysis_results
    id_map = {c['id']: c for c in analysis_results}
    
    for c in candidates:
        if c['id'] in id_map:
            # Update status from the referenced object (send_bulk_emails modifies in place)
            id_map[c['id']]['email_status'] = c.get('email_status', 'failed')
            id_map[c['id']]['meeting_link'] = c.get('meeting_link')
            id_map[c['id']]['test_link'] = c.get('test_link')
            
    save_history(analysis_results)

# --- New Endpoints ---

class ScheduleRequest(BaseModel):
    candidate_ids: List[str]
    interview_time: str

@app.post("/api/schedule")
async def schedule_interviews(req: ScheduleRequest):
    """Set interview time for candidates"""
    global analysis_results
    count = 0
    for c in analysis_results:
        if c['id'] in req.candidate_ids:
            c['interview_time'] = req.interview_time
            count += 1
    save_history(analysis_results)
    return {"message": f"Scheduled {count} candidates"}

class InviteRequest(BaseModel):
    candidate_ids: List[str]

@app.post("/api/invite")
async def send_invites(req: InviteRequest, background_tasks: BackgroundTasks):
    """Send email invites to specific candidates"""
    global analysis_results
    candidates_to_invite = [c for c in analysis_results if c['id'] in req.candidate_ids]
    
    if not candidates_to_invite:
        raise HTTPException(status_code=404, detail="No candidates found")
        
    # We assume job_title is same for batch or taken from first candidate
    # Ideally should be passed, but for simplicity taking from candidate data
    job_title = candidates_to_invite[0].get('job_role', 'Position')
    
    background_tasks.add_task(
        send_bulk_emails_and_update,
        candidates_to_invite,
        job_title
    )
    return {"message": f"Sending invites to {len(candidates_to_invite)} candidates"}

@app.get("/api/test/{candidate_id}")
async def get_test(candidate_id: str):
    """Get test questions for a candidate"""
    candidate = next((c for c in analysis_results if c['id'] == candidate_id), None)
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
        
    if candidate.get('test_status') == 'completed':
         return {"status": "completed", "message": "Test already completed"}

    # Return questions without correct answers
    questions = candidate.get('test_data')
    
    # Fallback: If no test data (e.g. old candidate or failed gen), generate it now
    if not questions:
        try:
             # Lazy import to avoid circular dependency issues if any
             from services.mcq_generator import generate_mcq_test
             
             # Use job_role or default to generic
             role = candidate.get('job_role') or "Software Engineer"
             description = f"Job Role: {role}. (Generated on demand)"
             
             print(f"Generating fallback test for {candidate['name']} ({role})")
             questions = generate_mcq_test(description, num_questions=10)
             
             candidate['test_data'] = questions
             save_history(analysis_results)
             
        except Exception as e:
             print(f"Error generating fallback test: {e}")
             questions = []

    sanitized_questions = []
    for q in questions:
        q_copy = q.copy()
        q_copy.pop('correct_answer', None)
        sanitized_questions.append(q_copy)
        
    return {"candidate_name": candidate['name'], "questions": sanitized_questions}

class TestSubmitRequest(BaseModel):
    answers: Dict[int, int] # question_id -> selected_option_index

@app.post("/api/test/{candidate_id}/submit")
async def submit_test(candidate_id: str, submit: TestSubmitRequest):
    """Submit test answers"""
    global analysis_results
    candidate = next((c for c in analysis_results if c['id'] == candidate_id), None)
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
        
    if candidate.get('test_status') == 'completed':
        raise HTTPException(status_code=400, detail="Test already completed")

    # Score
    questions = candidate.get('test_data', [])
    score_result = score_mcq_test(submit.answers, questions)
    
    # Update candidate
    candidate['test_status'] = 'completed'
    candidate['mcq_score'] = score_result['score_percent']
    
    # Update final score (50% interview, 50% technical initially, but interview score might be 0)
    # If interview score is 0, final score is just weighted MCQ? No, we will update final score when HR grades.
    # Logic: Final Score = (HR_Score + MCQ_Score) / 2
    candidate['final_score'] = (candidate.get('hr_score', 0) + candidate['mcq_score']) / 2
    
    save_history(analysis_results)
    return score_result

class ScoreRequest(BaseModel):
    hr_score: float

@app.post("/api/score/{candidate_id}")
async def submit_hr_score(candidate_id: str, req: ScoreRequest, background_tasks: BackgroundTasks):
    """Submit HR interview score (Out of 10)"""
    global analysis_results
    candidate = next((c for c in analysis_results if c['id'] == candidate_id), None)
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
        
    if req.hr_score > 10:
        raise HTTPException(status_code=400, detail="Score must be out of 10")

    candidate['hr_score'] = req.hr_score
    
    # Normalize MCQ (0-100) to 0-10
    mcq_val_10 = (candidate.get('mcq_score', 0) / 10)
    
    # Final Score (Average of HR and MCQ on 10-point scale)
    candidate['final_score'] = round((req.hr_score + mcq_val_10) / 2, 2)
    
    # Selection Logic
    if candidate['final_score'] > 7:
        candidate['hire_recommendation'] = "Selected"
        # Trigger Email
        # We need to import locally to avoid circular imports if any, or just at top
        from services.email_service import send_selection_email
        
        background_tasks.add_task(
            send_selection_email,
            candidate['email'],
            candidate['name'],
            candidate.get('job_role', 'Applicant')
        )
        msg = "Score updated. Candidate Selected! Email queued."
    else:
        candidate['hire_recommendation'] = "Rejected" if candidate['final_score'] < 5 else "On Hold"
        msg = "Score updated."
    
    save_history(analysis_results)
    return {
        "message": msg, 
        "final_score": candidate['final_score'],
        "status": candidate['hire_recommendation']
    }

@app.get("/api/results")
async def get_results():
    """Get all historical results"""
    return analysis_results

@app.delete("/api/history/{candidate_id}")
async def delete_candidate(candidate_id: str):
    """Delete a candidate from history"""
    global analysis_results
    initial_len = len(analysis_results)
    analysis_results = [c for c in analysis_results if c['id'] != candidate_id]
    
    if len(analysis_results) == initial_len:
        raise HTTPException(status_code=404, detail="Candidate not found")
        
    save_history(analysis_results)
    return {"message": "Deleted successfully"}

@app.get("/api/config")
async def get_config():
    """Get public configuration"""
    return {
        "app_name": "Jobs.AI",
        "version": "3.1"
    }

# Serve Frontend
os.makedirs("web", exist_ok=True)
app.mount("/", StaticFiles(directory="web", html=True), name="static")

if __name__ == "__main__":
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True)
