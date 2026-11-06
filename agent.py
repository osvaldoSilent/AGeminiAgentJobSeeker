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
        You are an autonomous AI Agent built by Osvaldo Isaac Garcia Amador.
        
        Candidate CV (Markdown):
        {cv_content}
        
        Target LinkedIn Post Snippet:
        {job_post_text}
        
        Instructions:
        1. Calculate a "fit_score" (integer 1-100) based on this snippet.
        2. If this looks like a job opportunity, write an engaging "subject".
        3. Write the "body". If the snippet contains an email, write a Cold Email. If it DOES NOT contain an email, write a short, punchy Direct Message (DM) meant for LinkedIn. State you are Osvaldo's AI Agent.
        
        Return ONLY a valid JSON: {{"fit_score": int, "subject": str, "body": str}}
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
                    # Intento 1: Servidor en Español
                    status, _ = imap.append('"[Gmail]/Borradores"', r'(\Draft)', internal_date, msg.as_bytes())
                    if status != 'OK':
                        raise imaplib.IMAP4.error("Fallo al guardar en Borradores")
                except imaplib.IMAP4.error:
                    # Intento 2: Servidor en Inglés
                    imap.append('"[Gmail]/Drafts"', r'(\Draft)', internal_date, msg.as_bytes())
                    
            logger.info("¡Éxito! El correo con el PDF está en tu carpeta de Borradores.")
            return True
        except Exception as e:
            logger.error(f"Error fatal de IMAP al guardar el borrador: {e}")
            return False
    def fetch_linkedin_posts(self, keywords="Senior Java Backend", location="Mexico", limit=3) -> list:
        """Busca publicaciones orgánicas usando OSINT en DuckDuckGo para evadir bloqueos de IP."""
        import re
        from duckduckgo_search import DDGS
        
        logger.info("Ejecutando Dorking en DuckDuckGo (Evasión Anti-Bot)...")
        
        # Ajustamos el Dork a la sintaxis que mejor procesa DuckDuckGo
        query = f'site:linkedin.com/posts OR site:linkedin.com/feed/update "we are hiring" OR "buscamos" "{keywords}" "{location}"'
        
        posts = []
        try:
            with DDGS() as ddgs:
                # Retorna un generador con diccionarios de resultados
                results = ddgs.text(query, max_results=limit)
                
                for r in results:
                    link = r.get("href", "")
                    snippet = r.get("body", "")
                    
                    if not link or "linkedin.com" not in link:
                        continue
                    
                    # Buscamos patrones de correo electrónico en el snippet
                    email_match = re.search(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', snippet)
                    extracted_email = email_match.group(0) if email_match else None
                    
                    logger.info(f"Post encontrado: {link}")
                    if extracted_email:
                        logger.info(f"¡Correo cazado!: {extracted_email}")
                    
                    posts.append({
                        "url": link,
                        "description": snippet,
                        "extracted_email": extracted_email
                    })
                    
        except Exception as e:
            logger.error(f"Error raspando con DuckDuckGo: {e}")
            
        return posts
    
if __name__ == "__main__":
    agent = JobSeekerAgent()
    cv_md = agent.load_cv_markdown("cv.md")
    test_recipient = os.environ.get("SMTP_USER")
    
    # 1. Scrapear las 3 vacantes más relevantes del día
    # Puedes ajustar los keywords (ej. "Spring Boot", "Tech Lead")
    real_jobs = agent.fetch_linkedin_posts(
        keywords="Senior Java Backend", 
        location="Mexico", 
        limit=3
    )
    
    if not real_jobs:
        logger.warning("No se encontraron vacantes hoy o LinkedIn bloqueó la petición.")
    
    # 2. Iterar sobre cada vacante, evaluarla y crear el borrador
    for job in real_jobs:
        logger.info(f"--- Evaluando: {job['title']} en {job['company']} ---")
        
        # Preparamos el texto para el LLM
        full_job_text = f"Title: {job['title']}\nCompany: {job['company']}\nURL: {job['url']}\nDescription: {job['description']}"
        
        # La IA analiza y redacta
        result = agent.generate_cold_email(full_job_text, cv_md)
        fit_score = result.get("fit_score", 0)
        
        logger.info(f"Fit Score Calculado para {job['company']}: {fit_score}%")
        
        # Filtro de calidad: Solo guarda borrador si pasas del 75%
        if fit_score >= 75 and test_recipient:
            # Agregamos la URL de la vacante al cuerpo del correo para tu propia referencia
            body_with_context = f"{result['body']}\n\n---\nNota interna: Vacante encontrada en {job['url']}"
            
            agent.save_as_draft_with_pdf(
                to_email=test_recipient,
                subject=result["subject"],
                body=body_with_context,
                pdf_path="cv.pdf"
            )
            logger.info("Borrador listo en Gmail.\n")
        else:
            logger.info("Descartada por bajo Fit Score.\n")