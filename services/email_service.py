"""
SMTP email service with batch processing and connection pooling.
Replaces SendGrid with Python's built-in SMTP library.
"""

import smtplib
import time
import uuid
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List, Dict, Tuple, Optional, Callable

from config import (
    SMTP_EMAIL, SMTP_PASSWORD, SMTP_SERVER, SMTP_PORT,
    EMAIL_DELAY_SECONDS, MAX_EMAIL_RETRIES
)


def generate_jitsi_link(job_title: str) -> str:
    """
    Generate a unique Jitsi meeting link.
    
    Args:
        job_title: Job title for the meeting room name
        
    Returns:
        Jitsi meeting URL
    """
    suffix = uuid.uuid4().hex[:8]
    room = f"{job_title.strip().replace(' ', '-')}-{suffix}"
    return f"https://meet.jit.si/{room}"


def send_email_smtp(
    to_email: str,
    candidate_name: str,
    job_title: str,
    meeting_link: str,
    ats_score: int,
    interview_time: str,
    test_link: str,
    smtp_connection: Optional[smtplib.SMTP] = None
) -> Tuple[bool, str]:
    """
    Send a single email via SMTP.
    
    Args:
        to_email: Recipient email address
        candidate_name: Candidate's name
        job_title: Job position title
        meeting_link: Jitsi meeting link
        ats_score: ATS score
        interview_time: Scheduled interview time
        test_link: Link to the MCQ test
        smtp_connection: Optional existing SMTP connection to reuse
        
    Returns:
        Tuple of (success, status_message)
    """
    if not SMTP_EMAIL or not SMTP_PASSWORD:
        return False, "SMTP not configured"
    
    subject = f"🎉 Interview Invitation - {job_title} Position"
    
    body = f"""Dear {candidate_name},

Congratulations! We are pleased to inform you that your application for the {job_title} position has been shortlisted.

Your Profile Score: {ats_score}/100

📅 Interview Scheduled: {interview_time}
📹 Interview Meeting Link: {meeting_link}

📝 Technical Assessment (Round 2):
Please complete the mandatory AI-based MCQ test before the interview.
Test Link: {test_link}

Our recruitment team is looking forward to meeting you.

Best regards,
Recruitment Team"""
    
    # Create message
    msg = MIMEMultipart()
    msg['From'] = SMTP_EMAIL
    msg['To'] = to_email
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain'))
    
    # Send email
    close_connection = False
    if smtp_connection is None:
        close_connection = True
        try:
            smtp_connection = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
            smtp_connection.starttls()
            smtp_connection.login(SMTP_EMAIL, SMTP_PASSWORD)
        except Exception as e:
            return False, f"Connection error: {str(e)}"
    
    try:
        smtp_connection.send_message(msg)
        if close_connection:
            smtp_connection.quit()
        return True, "Sent successfully"
    except Exception as e:
        if close_connection and smtp_connection:
            try:
                smtp_connection.quit()
            except:
                pass
        return False, f"Send error: {str(e)}"


def send_bulk_emails(
    candidates: List[Dict],
    job_title: str,
    progress_callback: Optional[Callable[[int, int, str, bool], None]] = None
) -> Dict[str, any]:
    """
    Send emails to multiple candidates with connection pooling and retry logic.
    
    Args:
        candidates: List of candidate dictionaries
        job_title: Job position title
        progress_callback: Optional callback(current, total, name, success)
        
    Returns:
        Dictionary with success_count, failed_count, and results list
    """
    if not SMTP_EMAIL or not SMTP_PASSWORD:
        return {
            "success_count": 0,
            "failed_count": len(candidates),
            "error": "SMTP not configured",
            "results": []
        }
    
    # Filter candidates with valid emails (just in case)
    candidates_with_email = [c for c in candidates if c.get('email')]
    
    if not candidates_with_email:
        return {
            "success_count": 0,
            "failed_count": 0,
            "error": "No candidates with valid emails",
            "results": []
        }
    
    success_count = 0
    failed_count = 0
    results = []
    total = len(candidates_with_email)
    
    # Create SMTP connection pool (reuse connection)
    smtp_connection = None
    try:
        smtp_connection = smtplib.SMTP(SMTP_SERVER, SMTP_PORT, timeout=30)
        smtp_connection.starttls()
        smtp_connection.login(SMTP_EMAIL, SMTP_PASSWORD)
    except Exception as e:
        return {
            "success_count": 0,
            "failed_count": total,
            "error": f"SMTP connection failed: {str(e)}",
            "results": []
        }
    
    # Send emails using pooled connection
    for idx, candidate in enumerate(candidates_with_email):
        # Generate meeting link if not exists
        if not candidate.get('meeting_link'):
            candidate['meeting_link'] = generate_jitsi_link(job_title)
            
        # Get interview details
        interview_time = candidate.get('interview_time', 'To be scheduled')
        test_link = candidate.get('test_link', '#')
        
        # Retry logic
        success = False
        last_error = ""
        
        for attempt in range(MAX_EMAIL_RETRIES):
            try:
                success, message = send_email_smtp(
                    candidate['email'],
                    candidate['name'],
                    job_title,
                    candidate['meeting_link'],
                    candidate['ats_score'],
                    interview_time,
                    test_link,
                    smtp_connection
                )
                
                if success:
                    break
                else:
                    last_error = message
                    if attempt < MAX_EMAIL_RETRIES - 1:
                        time.sleep(1)  # Wait before retry
                        
            except Exception as e:
                last_error = str(e)
                if attempt < MAX_EMAIL_RETRIES - 1:
                    time.sleep(1)
        
        # Update candidate status
        if success:
            candidate['email_sent'] = True
            candidate['email_status'] = 'sent'
            success_count += 1
        else:
            candidate['email_sent'] = False
            candidate['email_status'] = f'failed: {last_error}'
            failed_count += 1
        
        results.append({
            "name": candidate['name'],
            "email": candidate['email'],
            "success": success,
            "message": "Sent" if success else last_error
        })
        
        # Progress callback
        if progress_callback:
            progress_callback(idx + 1, total, candidate['name'], success)
        
        # Rate limiting (avoid spam filters)
        if idx < total - 1:  # Don't delay after last email
            time.sleep(EMAIL_DELAY_SECONDS)
    
    # Close connection
    try:
        smtp_connection.quit()
    except:
        pass
    
    return {
        "success_count": success_count,
        "failed_count": failed_count,
        "results": results
    }


def test_smtp_connection() -> Tuple[bool, str]:
    """
    Test SMTP connection and credentials.
    
    Returns:
        Tuple of (success, message)
    """
    if not SMTP_EMAIL or not SMTP_PASSWORD:
        return False, "SMTP credentials not configured in .env file"
    
    try:
        smtp = smtplib.SMTP(SMTP_SERVER, SMTP_PORT, timeout=10)
        smtp.starttls()
        smtp.login(SMTP_EMAIL, SMTP_PASSWORD)
        smtp.quit()
        return True, "SMTP connection successful"
    except Exception as e:
        return False, f"SMTP connection failed: {str(e)}"
