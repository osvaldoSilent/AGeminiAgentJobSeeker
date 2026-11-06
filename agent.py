import os
import json
import logging
import time
import imaplib
import requests
from email.message import EmailMessage
from pathlib import Path

# Configuración de logs para entornos CI/CD (GitHub Actions)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("JobSeekerAIAgent")

class JobSeekerAgent:
    def __init__(self):
        """Inicializa el agente y valida las credenciales de entorno."""
        self.api_key = os.environ.get("GEMINI_API_KEY")
        self.smtp_user = os.environ.get("SMTP_USER")
        self.smtp_pass = os.environ.get("SMTP_APP_PASSWORD")

        if not self.api_key:
            raise ValueError("La variable de entorno GEMINI_API_KEY no está configurada.")
        
        logger.info("Agente IA inicializado correctamente.")

    def load_cv_markdown(self, md_path: str = "cv.md") -> str:
        """Lee el CV en formato Markdown para inyectarlo como contexto base."""
        path = Path(md_path)
        if not path.exists():
            logger.warning(f"No se encontró '{md_path}'. Usando perfil de respaldo.")
            return "Senior Software Engineer & Technical Lead (Java, Spring Boot, Microservices, GCP)."
        return path.read_text(encoding="utf-8")

    def generate_cold_email(self, job_post_text: str, cv_content: str) -> dict:
        """Genera el asunto y cuerpo del correo conectándose a la API REST de Gemini."""
        logger.info("Generando correo persuasivo vía Gemini REST API...")
        
        prompt = f"""
        You are an autonomous AI Agent built and deployed by Osvaldo Isaac Garcia Amador.
        
        Candidate CV (Markdown):
        {cv_content}
        
        Target Job Post:
        {job_post_text}
        
        Instructions:
        1. Calculate a "fit_score" (integer 1-100) evaluating how well the post matches Osvaldo's profile.
        2. Write an engaging, concise email "subject".
        3. Write the email "body" (maximum 3 short paragraphs). Openly state that you are Osvaldo's Autonomous AI Agent running on a daily automated pipeline, reaching out on his behalf with his PDF resume attached.
        
        Output Requirements:
        Return ONLY a valid JSON object with keys: "fit_score" (int), "subject" (str), and "body" (str).
        """
        
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.8-flash:generateContent?key={self.api_key}"
        headers = {'Content-Type': 'application/json'}
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"responseMimeType": "application/json"}
        }
        
        max_retries = 5
        for attempt in range(max_retries):
            try:
                # Timeout nativo y estricto de 15 segundos por intento
                response = requests.post(url, headers=headers, json=payload, timeout=15)
                response.raise_for_status() 
                
                data = response.json()
                raw_text = data["candidates"][0]["content"]["parts"][0]["text"]
                return json.loads(raw_text)
                
            except Exception as e:
                error_msg = str(e).lower()
                if attempt < max_retries - 1:
                    wait_time = 5 * (2 ** attempt)
                    logger.warning(f"Error de red ({error_msg[:25]}...). Reintentando en {wait_time}s...")
                    time.sleep(wait_time)
                    continue
                
                logger.error(f"Gemini API colapsó totalmente: {str(e)}. Activando Fallback Estático.")
                # Graceful Degradation: Plantilla por defecto si falla la IA
                return {
                    "fit_score": 85,
                    "subject": "Senior Java Backend Engineer / Tech Lead - Osvaldo Garcia",
                    "body": "Hello,\n\nI am writing to express my interest in the backend engineering position. As a Technical Lead based in Mexico with extensive experience architecting distributed microservices using Java, Spring Boot, and GCP, I am confident in my ability to bring immediate value to your team.\n\nPlease find my resume attached for your review. I look forward to the possibility of discussing this role further.\n\nBest regards,\nOsvaldo Garcia (Automated Pipeline Fallback)"
                }

    def save_as_draft_with_pdf(self, to_email: str, subject: str, body: str, pdf_path: str = "cv.pdf") -> bool:
        """Construye el correo Mime, adjunta el PDF y lo guarda en Borradores usando IMAP."""
        if not self.smtp_user or not self.smtp_pass:
            logger.error("Faltan las credenciales SMTP_USER / SMTP_APP_PASSWORD.")
            return False

        pdf_file = Path(pdf_path)
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = f"Osvaldo Garcia <{self.smtp_user}>"
        msg["To"] = to_email
        msg.set_content(body)

        if pdf_file.exists():
            with open(pdf_file, "rb") as f:
                msg.add_attachment(
                    f.read(), 
                    maintype="application", 
                    subtype="pdf", 
                    filename="Osvaldo_Garcia_Senior_Software_Engineer_CV.pdf"
                )
        else:
            logger.warning(f"El archivo '{pdf_path}' no existe. Guardando borrador sin adjunto.")

        try:
            logger.info("Conectando a Gmail IMAP (Puerto 993) para guardar el borrador...")
            with imaplib.IMAP4_SSL("imap.gmail.com", 993) as imap:
                imap.login(self.smtp_user, self.smtp_pass)
                internal_date = imaplib.Time2Internaldate(time.time())
                
                try:
                    # Intento 1: Servidor en Inglés
                    imap.append('[Gmail]/Drafts', r'(\Draft)', internal_date, msg.as_bytes())
                except imaplib.IMAP4.error:
                    # Intento 2: Servidor en Español
                    imap.append('[Gmail]/Borradores', r'(\Draft)', internal_date, msg.as_bytes())
                    
            logger.info("¡Éxito! El correo con el PDF está en tu carpeta de Borradores.")
            return True
        except Exception as e:
            logger.error(f"Error fatal de IMAP al guardar el borrador: {e}")
            return False

if __name__ == "__main__":
    agent = JobSeekerAgent()
    cv_md = agent.load_cv_markdown("cv.md")
    
    # Vacante simulada para probar el pipeline
    dummy_post = """
    Hiring! Looking for a Senior Java Backend Developer / Tech Lead based in Mexico (100% Remote) 
    with strong English skills, Spring Boot, microservices, and GCP experience. 
    Send your resume to hiring@example.com
    """
    
    test_recipient = os.environ.get("SMTP_USER")
    
    # 1. Analizar post y redactar
    result = agent.generate_cold_email(dummy_post, cv_md)
    fit_score = result.get("fit_score", 0)
    logger.info(f"Fit Score Calculado: {fit_score}%")
    
    # 2. Guardar en borradores si es un buen match
    if fit_score >= 75 and test_recipient:
        agent.save_as_draft_with_pdf(
            to_email=test_recipient,
            subject=result["subject"],
            body=result["body"],
            pdf_path="cv.pdf"
        )