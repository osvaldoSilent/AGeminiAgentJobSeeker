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

class JobSeekerAgent:
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
        3. Write the email "body" (maximum 3 short paragraphs). Openly state that you are Osvaldo's Autonomous AI Agent running on a daily automated pipeline, reaching out on his behalf with his PDF resume attached. Connect his specific strengths from the CV to what they are looking for.
        
        Output Requirements:
        Return ONLY a valid JSON object with keys: "fit_score" (int), "subject" (str), and "body" (str).
        """
        
        try:
            response = self.model.generate_content(prompt)
            return json.loads(response.text)
        except Exception as e:
            logger.error(f"Gemini generation failed: {e}")
            return {"fit_score": 0, "subject": "", "body": ""}

    def send_email_with_pdf(self, to_email: str, subject: str, body: str, pdf_path: str = "cv.pdf") -> bool:
        """Sends an email with the PDF resume attached via Gmail SMTP."""
        if not self.smtp_user or not self.smtp_pass:
            logger.error("SMTP credentials (SMTP_USER / SMTP_APP_PASSWORD) are missing.")
            return False

        pdf_file = Path(pdf_path)
        if not pdf_file.exists():
            logger.error(f"Attachment file '{pdf_path}' not found in the repository.")
            return False

        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = f"Osvaldo Garcia (AI Agent) <{self.smtp_user}>"
        msg["To"] = to_email
        msg.set_content(body)

        # Read and attach the PDF binary payload
        with open(pdf_file, "rb") as f:
            pdf_data = f.read()
            msg.add_attachment(
                pdf_data,
                maintype="application",
                subtype="pdf",
                filename="Osvaldo_Garcia_Senior_Software_Engineer_CV.pdf"
            )

        try:
            logger.info(f"Connecting to Gmail SMTP to dispatch email to {to_email}...")
            # Port 465 uses implicit SSL/TLS (cleaner and faster than port 587 STARTTLS)
            with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
                server.login(self.smtp_user, self.smtp_pass)
                server.send_message(msg)
            logger.info("Email dispatched successfully!")
            return True
        except Exception as e:
            logger.error(f"SMTP error while sending email: {e}")
            return False

if __name__ == "__main__":
    agent = JobSeekerAgent()
    cv_md = agent.load_cv_markdown("cv.md")
    
    # Simulated LinkedIn post for end-to-end testing
    dummy_post = """
    Hiring! Looking for a Senior Java Backend Developer / Tech Lead based in Mexico (100% Remote) 
    with strong English skills, Spring Boot, microservices, and GCP experience. 
    Send your resume to hiring@example.com
    """
    
    # Send the first test to your own email address to inspect how it lands in the inbox
    test_recipient = os.environ.get("SMTP_USER")
    
    result = agent.generate_cold_email(dummy_post, cv_md)
    fit_score = result.get("fit_score", 0)
    logger.info(f"Calculated Fit Score: {fit_score}%")
    
    if fit_score >= 75 and test_recipient:
        agent.send_email_with_pdf(
            to_email=test_recipient,
            subject=result["subject"],
            body=result["body"],
            pdf_path="cv.pdf"
        )