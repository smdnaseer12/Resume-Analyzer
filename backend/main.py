from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import PyPDF2
import io
import json
from datetime import datetime
import re

SKILL_SET = {
    "python", "java", "c++", "machine learning", "data analysis", "css", "javascript", "node.js",
    "html", "sql", "git", "github", "react", "angular", "docker", "aws", "azure", "linux",
    "tensorflow", "keras", "pandas", "numpy", "scikit-learn", "flask", "django", "excel",
    "power bi", "tableau", "communication", "leadership", "project management"
    # Add more as needed!
}

app = FastAPI(title="Resume Analyzer API")

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "https://resume-analyzer-sable-zeta.vercel.app"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Simple text processing without SpaCy

class ResumeAnalysis(BaseModel):
    skills: List[str]
    education: List[str]
    experience: List[str]
    certifications: List[str]
    recommendations: Optional[List[str]] = None
    score: Optional[int] = None
    issues: Optional[List[str]] = None

def extract_text_from_pdf(pdf_file: bytes) -> str:
    try:
        pdf_reader = PyPDF2.PdfReader(io.BytesIO(pdf_file))
        text = ""
        for page in pdf_reader.pages:
            text += page.extract_text()
        return text
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error reading PDF: {str(e)}")

def extract_skills(text: str) -> list:
    found_skills = []
    text_lower = text.lower()
    for skill in SKILL_SET:
        if skill.lower() in text_lower:
            found_skills.append(skill)
    return found_skills

def extract_section_by_header(text, header, next_headers=None):
    """
    Extract lines under a section header until the next header or end of text.
    More robust: allows for optional whitespace/lines after the header.
    """
    if next_headers is None:
        next_headers = []
    # Allow for up to 3 lines of whitespace or non-uppercase after the header
    pattern = rf"{header}\s*\n(?:.*\n){{0,3}}(.*?)(\n(?:{'|'.join(next_headers)})|$)"
    match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
    if match:
        section_text = match.group(1).strip()
        lines = [line.strip() for line in section_text.splitlines() if line.strip()]
        if lines:
            return lines
    return []

# Helper to filter out contact info lines
def is_contact_info(line):
    line_lower = line.lower()
    # Add more patterns as needed
    return (
        '@' in line_lower or
        'linkedin' in line_lower or
        re.search(r'\+?\d[\d\- ]{7,}', line_lower) or
        'ambiti dhanush raj' in line_lower
    )

def extract_education(text):
    lines = extract_section_by_header(
        text,
        header="EDUCATION",
        next_headers=["CERTIFICATIONS", "PROJECTS", "KEY SKILLS AND TOOLS", "CAREER OBJECTIVE"]
    )
    education = []
    degree_keywords = ["bachelor", "master", "phd", "b.tech", "m.tech", "b.sc", "m.sc", "intermediate", "grade", "university", "college", "school"]
    for line in lines:
        if is_contact_info(line):
            continue
        # Only include lines with degree, institution, or year patterns
        if any(word in line.lower() for word in degree_keywords) or re.search(r"(19|20)\\d{2}", line):
            education.append(line.strip())
    return education

def extract_experience(text):
    lines = extract_section_by_header(
        text,
        header="PROJECTS",
        next_headers=["EDUCATION", "CERTIFICATIONS", "KEY SKILLS AND TOOLS", "CAREER OBJECTIVE"]
    )
    experience = []
    exp_keywords = ["project", "developed", "implemented", "machine learning", "web app", "description", "kaggle", "intern", "engineer", "developer", "role", "position"]
    for line in lines:
        if is_contact_info(line):
            continue
        # Only include lines with experience/project keywords or year patterns
        if any(word in line.lower() for word in exp_keywords) or re.search(r"(19|20)\\d{2}", line):
            experience.append(line.lstrip('•').strip())
    return experience

def extract_certifications(text):
    lines = extract_section_by_header(
        text,
        header="CERTIFICATIONS",
        next_headers=["EDUCATION", "PROJECTS", "KEY SKILLS AND TOOLS", "CAREER OBJECTIVE"]
    )
    certifications = []
    cert_keywords = ["certified", "certification", "certificate", "coursera", "udemy", "infosys", "exam", "award"]
    for line in lines:
        if is_contact_info(line):
            continue
        # Only include lines with certification/award keywords
        if any(word in line.lower() for word in cert_keywords):
            certifications.append(line.lstrip('•').strip())
    return certifications

def score_resume(skills, education, experience, certifications):
    score = 0
    # Skills: up to 80 points (8 points per skill, max 10 skills)
    score += min(len(skills), 10) * 8
    # Education: 5 points if present
    if education:
        score += 5
    # Experience: 5 points if present
    if experience:
        score += 5
    # Certifications: 5 points if present
    if certifications:
        score += 5
    # Ensure a minimum score of 60 if there are any skills
    if score < 60 and skills:
        score = 60
    return min(score, 100), []

def analyze_resume(text: str) -> ResumeAnalysis:
    skills = extract_skills(text)
    education = extract_education(text)
    experience = extract_experience(text)
    certifications = extract_certifications(text)
    recommendations = []
    if len(skills) > 0:
        recommendations.append(f"Based on your skills in {', '.join(skills[:3])}, consider roles in Software Development")
    score, issues = score_resume(skills, education, experience, certifications)
    return ResumeAnalysis(
        skills=skills,
        education=education,
        experience=experience,
        certifications=certifications,
        recommendations=recommendations,
        score=score,
        issues=issues
    )

@app.post("/api/analyze", response_model=ResumeAnalysis)
async def analyze_resume_endpoint(file: UploadFile = File(...)):
    if not file.filename.endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are allowed")
    
    contents = await file.read()
    text = extract_text_from_pdf(contents)
    analysis = analyze_resume(text)
    return analysis

@app.get("/api/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

if __name__ == "__main__":
    import uvicorn
    import os
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
