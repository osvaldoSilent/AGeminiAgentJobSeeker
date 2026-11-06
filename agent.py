import os
import json
import logging
import time
import imaplib
import requests
import re
import email.utils
from email.message import EmailMessage
from pathlib import Path
from ddgs import DDGS

# Configure structured logging for CI/CD environments (GitHub Actions)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("JobSeekerAIAgent")


class JobSeekerAgent:
    """Autonomous OSINT & Gemini AI agent that discovers LinkedIn hiring posts and saves tailored Gmail drafts."""

    def __init__(self):
        """Initializes the agent and validates required environment credentials."""
        self.api_key = os.environ.get("GEMINI_API_KEY")
        self.smtp_user = os.environ.get("SMTP_USER")
        self.smtp_pass = os.environ.get("SMTP_APP_PASSWORD")

        if not self.api_key:
            raise ValueError("Environment variable GEMINI_API_KEY is not configured.")

        logger.info(
            f"[INIT] Agent initialized | smtp_user={self.smtp_user} | "
            f"gemini_key_present={bool(self.api_key)} | smtp_pass_present={bool(self.smtp_pass)}"
        )

    def load_cv_markdown(self, md_path: str = "cv.md") -> str:
        """Loads the candidate CV in Markdown format to inject as base prompt context."""
        path = Path(md_path)
        if not path.exists():
            fallback_cv = "Senior Software Engineer & Technical Lead (Java, Spring Boot, Microservices, GCP)."
            logger.warning(f"[CV] File '{md_path}' not found. Using fallback profile: '{fallback_cv}'")
            return fallback_cv

        content = path.read_text(encoding="utf-8")
        logger.info(f"[CV] Loaded '{md_path}' ({len(content)} chars)")
        return content

    def generate_cold_email(self, job_post_text: str, cv_content: str) -> dict:
        """Evaluates job fit and generates outreach copy using a cascading fallback pattern across Gemini models."""
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

        headers = {'Content-Type': 'application/json'}
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"responseMimeType": "application/json"}
        }

        # Cascading fallback architecture: ordered from primary to lightweight backup model
        models_to_try = ["gemini-3.8-flash", "gemini-3.8-flash-8b"]
        max_retries = 3  # 3 attempts per model (6 total before static template fallback)

        for model in models_to_try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={self.api_key}"

            for attempt in range(1, max_retries + 1):
                start_ts = time.perf_counter()
                try:
                    response = requests.post(url, headers=headers, json=payload, timeout=15)
                    elapsed = time.perf_counter() - start_ts
                    response.raise_for_status()

                    data = response.json()
                    raw_text = data["candidates"][0]["content"]["parts"][0]["text"]
                    parsed = json.loads(raw_text)

                    logger.info(
                        f"[GEMINI] Success | model={model} | attempt={attempt}/{max_retries} | "
                        f"http_status={response.status_code} | latency={elapsed:.2f}s | "
                        f"fit_score={parsed.get('fit_score')}% | subject=\"{parsed.get('subject')}\""
                    )
                    return parsed

                except Exception as e:
                    elapsed = time.perf_counter() - start_ts
                    http_details = getattr(getattr(e, "response", None), "text", "") or str(e)
                    if attempt < max_retries:
                        wait_time = 3 * (2 ** (attempt - 1))  # Exponential backoff: 3s, 6s
                        logger.warning(
                            f"[GEMINI] Transient failure | model={model} | attempt={attempt}/{max_retries} | "
                            f"latency={elapsed:.2f}s | error={http_details} | retrying_in={wait_time}s"
                        )
                        time.sleep(wait_time)
                    else:
                        logger.error(
                            f"[GEMINI] Model exhausted retries | model={model} | "
                            f"attempts={max_retries} | last_error={http_details}"
                        )

        logger.error("[GEMINI] All AI models failed. Activating static template fallback.")
        return {
            "fit_score": 85,
            "subject": "Senior Java Backend Engineer / Tech Lead - Osvaldo Garcia",
            "body": "Hello,\n\nI am writing to express my interest in the backend engineering position. As a Technical Lead based in Mexico with extensive experience architecting distributed microservices using Java, Spring Boot, and GCP, I am confident in my ability to bring immediate value to your team.\n\nPlease find my resume attached for your review. I look forward to the possibility of discussing this role further.\n\nBest regards,\nOsvaldo Garcia (Automated Pipeline Fallback)"
        }

    def save_as_draft_with_pdf(self, to_email: str, subject: str, body: str, pdf_path: str = "cv.pdf") -> bool:
        """Builds a MIME email message, attaches the PDF resume, and appends it to Gmail Drafts via IMAP SSL."""
        if not self.smtp_user or not self.smtp_pass:
            logger.error("[IMAP] Missing SMTP_USER or SMTP_APP_PASSWORD credentials. Cannot save draft.")
            return False

        pdf_file = Path(pdf_path)
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = f"Osvaldo Garcia <{self.smtp_user}>"
        msg["To"] = to_email
        msg["Date"] = email.utils.formatdate(localtime=True)
        msg.set_content(body)

        # Attach PDF resume if present on disk
        if pdf_file.exists():
            pdf_bytes = pdf_file.read_bytes()
            attachment_name = "Osvaldo_Garcia_Senior_Software_Engineer_CV.pdf"
            msg.add_attachment(
                pdf_bytes,
                maintype="application",
                subtype="pdf",
                filename=attachment_name
            )
            logger.info(f"[MIME] Attached PDF '{pdf_path}' ({len(pdf_bytes) / 1024:.1f} KB) as '{attachment_name}'")
        else:
            logger.warning(f"[MIME] PDF file '{pdf_path}' not found. Proceeding with text-only draft.")

        try:
            with imaplib.IMAP4_SSL("imap.gmail.com", 993) as imap:
                imap.login(self.smtp_user, self.smtp_pass)
                internal_date = imaplib.Time2Internaldate(time.time())
                target_folder = '"[Gmail]/Borradores"'

                try:
                    # Primary attempt: Spanish Gmail Drafts folder with Draft and Seen flags
                    status, response_data = imap.append(target_folder, r'(\Draft \Seen)', internal_date, msg.as_bytes())
                    if status != 'OK':
                        raise imaplib.IMAP4.error(f"APPEND failed on {target_folder}: {response_data}")
                except imaplib.IMAP4.error:
                    # Fallback attempt: English Gmail Drafts folder
                    target_folder = '"[Gmail]/Drafts"'
                    status, response_data = imap.append(target_folder, r'(\Draft \Seen)', internal_date, msg.as_bytes())

            logger.info(
                f"[IMAP] Draft saved | folder={target_folder} | status={status} | "
                f"from={self.smtp_user} | to={to_email} | subject=\"{subject}\""
            )
            return True
        except Exception as e:
            logger.error(f"[IMAP] Fatal error saving draft for to={to_email}: {e}")
            return False

    def fetch_linkedin_posts(self, keywords="Senior Java Backend", location="Mexico", limit=3) -> list:
        """Searches organic LinkedIn hiring posts using OSINT dorking via DuckDuckGo (anti-bot evasion)."""
        query = f'site:linkedin.com/posts "we are hiring" {keywords} {location}'
        logger.info(f"[OSINT] Executing DDGS dork query='{query}' | max_results={limit}")

        posts = []
        try:
            with DDGS() as ddgs_client:
                results = ddgs_client.text(query, max_results=limit)

                for idx, r in enumerate(results, start=1):
                    link = r.get("href", "")
                    snippet = r.get("body", "")

                    if not link or "linkedin.com" not in link:
                        logger.info(f"[OSINT #{idx}] Skipped non-LinkedIn URL: {link}")
                        continue

                    # Extract recruiter email address from post snippet when present
                    email_match = re.search(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', snippet)
                    extracted_email = email_match.group(0) if email_match else None

                    logger.info(
                        f"[OSINT #{idx}] Captured post | url={link} | "
                        f"extracted_email={extracted_email or 'NONE'} | snippet=\"{snippet}\""
                    )

                    posts.append({
                        "url": link,
                        "description": snippet,
                        "extracted_email": extracted_email
                    })

        except Exception as e:
            logger.error(f"[OSINT] Error scraping results with ddgs: {e}")

        logger.info(f"[OSINT] Discovery finished | valid_linkedin_posts={len(posts)}")
        return posts


if __name__ == "__main__":
    SEARCH_KEYWORDS = "Java Spring Boot"
    SEARCH_LOCATION = "Mexico"
    SEARCH_LIMIT = 3
    FIT_SCORE_THRESHOLD = 75

    agent = JobSeekerAgent()
    cv_md = agent.load_cv_markdown("cv.md")
    my_email = os.environ.get("SMTP_USER")

    # Stage 1: Fetch organic LinkedIn hiring posts via OSINT
    posts = agent.fetch_linkedin_posts(
        keywords=SEARCH_KEYWORDS,
        location=SEARCH_LOCATION,
        limit=SEARCH_LIMIT
    )

    if not posts:
        logger.warning("[PIPELINE] No relevant LinkedIn posts found today. Exiting.")

    drafts_saved = 0
    discarded_count = 0

    # Stage 2: Evaluate each post and create Gmail drafts for high-fit matches
    for idx, post in enumerate(posts, start=1):
        logger.info(f"[EVAL {idx}/{len(posts)}] Processing post url={post['url']}")

        # Build structured prompt context from scraped post metadata
        context_text = (
            f"URL: {post['url']}\n"
            f"Snippet: {post['description']}\n"
            f"Extracted Email: {post['extracted_email'] or 'NONE'}"
        )

        result = agent.generate_cold_email(context_text, cv_md)
        fit_score = result.get("fit_score", 0)

        if fit_score >= FIT_SCORE_THRESHOLD:
            # Route to recruiter email if extracted; otherwise self-address as a LinkedIn DM draft
            has_recruiter_email = bool(post["extracted_email"])
            outreach_mode = "COLD_EMAIL" if has_recruiter_email else "LINKEDIN_DM"
            target_email = post["extracted_email"] if has_recruiter_email else my_email

            if not has_recruiter_email:
                result["subject"] = f"[LINKEDIN DM] Responder a: {post['url']}"

            body_with_link = f"{result['body']}\n\n---\nPost original: {post['url']}"

            logger.info(
                f"[DECISION {idx}/{len(posts)}] ACCEPTED ({fit_score}% >= {FIT_SCORE_THRESHOLD}%) | "
                f"mode={outreach_mode} | target_email={target_email} | generated_body:\n{body_with_link}"
            )

            if agent.save_as_draft_with_pdf(
                to_email=target_email,
                subject=result["subject"],
                body=body_with_link,
                pdf_path="cv.pdf"
            ):
                drafts_saved += 1
        else:
            discarded_count += 1
            logger.info(
                f"[DECISION {idx}/{len(posts)}] DISCARDED ({fit_score}% < {FIT_SCORE_THRESHOLD}%) | url={post['url']}"
            )

        # Rate limiter: pause 5 seconds between evaluations to respect Gemini free-tier RPM limits
        if idx < len(posts):
            time.sleep(5)

    logger.info(
        f"[SUMMARY] Pipeline finished | total_evaluated={len(posts)} | "
        f"drafts_saved={drafts_saved} | discarded={discarded_count}"
    )
