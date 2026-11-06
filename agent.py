import os
import json
import logging
import smtplib
from email.message import EmailMessage
from pathlib import Path
import google.generativeai as genai
from google.generativeai.types import generation_types

# Configure logging for CI/CD environments
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("JobSeekerAIAgent")

class AGeminiAgentJobSeeker:
    def __init__(self):
        """Initializes the AI agent and authenticates with Google Gemini API."""
        self.api_key = os.environ.get("GEMINI_API_KEY")
        self.smtp_user = os.environ.get("SMTP_USER")
        self.smtp_pass = os.environ.get("SMTP_APP_PASSWORD")

        if not self.api_key:
            raise ValueError("GEMINI_API_KEY environment variable is missing.")
            
        genai.configure(api_key=self.api_key)
        self.model = genai.GenerativeModel(
            'gemini-2.5-flash',
            generation_config=generation_types.GenerationConfig(
                response_mime_type="application/json"
            )
        )
        logger.info("AI Agent initialized successfully.")

    def load_cv_markdown(self, md_path: str = "cv.md") -> str:
        """Reads the markdown CV so the LLM has real context."""
        path = Path(md_path)
        if not path.exists():
            logger.warning(f"{md_path} not found. Using fallback profile summary.")
            return "Senior Software Engineer & Technical Lead (Java, Spring Boot, Microservices, Hexagonal Architecture, GCP, CI/CD)."
        return path.read_text(encoding="utf-8")

    def generate_cold_email(self, job_post_text: str, cv_content: str) -> dict:
        """Evaluates the post against the CV and generates a custom subject and body."""
        logger.info("Generating customized cold email with Gemini...")
        
        prompt = f"""
        You are an autonomous AI Agent built and deployed by Osvaldo Isaac Garcia Amador.
        
        Candidate CV (Markdown):
        {cv_content}
        
        Target Job Post / Recruiter Announcement:
        {job_post_text}
        
        Instructions:
        1. Calculate a "fit_score" (integer 1-100) evaluating how well the post matches Osvaldo's profile.
        2. Write an engaging, concise email "subject" (in English if the post is in English, or Spanish if the post is in Spanish, highlighting Senior Java / Tech Lead skills).
        3. Write the email "body" (maximum 3 short paragraphs). Openly state that you are Osvaldo'