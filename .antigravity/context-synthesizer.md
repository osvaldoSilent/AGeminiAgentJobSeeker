# Role & Purpose
You are the **Context Synthesizer** for `aGeminiAgentJobSeeker` (**JobSeeker-aGeminiAgent**).
Your purpose is to provide an immediate, high-density architectural snapshot of the autonomous job-hunting AI agent so any AI agent session starts with complete context without needing to scan the entire repository, and to update the **Iteration Log** after every major milestone.

---

# 1. Project Snapshot (`aGeminiAgentJobSeeker`)
- **Stack:** Python 3.12, `ddgs` (DuckDuckGo OSINT Search), `requests` (Direct Google Gemini REST API), native `imaplib` & `email.message` (Gmail IMAP SSL Draft injection).
- **Architecture & Safety Model:** **Human-in-the-loop** with a strict **Zero-Send Policy** (no SMTP sending logic exists in the codebase; all generated messages are appended exclusively as `(\Draft \Seen)` in Gmail Drafts).
- **Resilience Patterns:**
  - **Cascading Fallback:** `gemini-3.8-flash` (3 retries) $\rightarrow$ `gemini-3.8-flash-8b` (3 retries) $\rightarrow$ Static Fallback Template (`fit_score: 85`).
  - **Exponential Backoff & Timeouts:** 15s strict HTTP timeout per Gemini REST call with incremental backoff (`3s`, `6s`).
  - **Rate Limiter:** 5s sleep between evaluated job posts (`if idx < len(posts)`) to respect free-tier Gemini RPM limits.
  - **Bilingual IMAP Folder Resolution:** Automatically tries `"[Gmail]/Borradores"` first and falls back to `"[Gmail]/Drafts"`.
- **CI/CD & Automation:** GitHub Actions (`.github/workflows/daily.job.yml`) running daily via Cron (`0 8 * * *` UTC) and supporting manual execution (`workflow_dispatch`).

---

# 2. Component & Workflow Map

## Core Engine (`agent.py` — `JobSeekerAgent`)
- **`__init__()`**: Validates `GEMINI_API_KEY`, loads `SMTP_USER` and `SMTP_APP_PASSWORD`, and logs `[INIT]` status.
- **`load_cv_markdown(md_path="cv.md")`**: Reads the candidate's Markdown resume (`cv.md`) for prompt context injection (or falls back to a default Senior Java/Spring Boot/GCP summary) and logs `[CV]`.
- **`fetch_linkedin_posts(keywords, location, limit)`**: Executes OSINT dork queries (`site:linkedin.com/posts "we are hiring" <keywords> <location>`) via `DDGS().text()`, filters valid LinkedIn URLs, extracts recruiter emails via regex, and logs `[OSINT]` / `[OSINT #N]`.
- **`generate_cold_email(job_post_text, cv_content)`**: Calls `https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent` with `responseMimeType: "application/json"`, returning `{"fit_score": int, "subject": str, "body": str}` (Cold Email if recruiter email is present; LinkedIn DM if absent) and logging `[GEMINI]`.
- **`save_as_draft_with_pdf(to_email, subject, body, pdf_path="cv.pdf")`**: Builds a MIME `EmailMessage`, attaches `cv.pdf` as `Osvaldo_Garcia_Senior_Software_Engineer_CV.pdf` (`[MIME]`), connects to `imap.gmail.com:993` over SSL, appends the draft with `(\Draft \Seen)` flags, and logs `[IMAP]`.
- **Main Orchestration (`if __name__ == "__main__":`)**:
  - Configurable constants: `SEARCH_KEYWORDS = "Java Spring Boot"`, `SEARCH_LOCATION = "Mexico"`, `SEARCH_LIMIT = 3`, `FIT_SCORE_THRESHOLD = 75`.
  - Evaluates each post (`[EVAL i/N]`), logs verdict and full generated body (`[DECISION i/N]`), saves drafts when `fit_score >= 75`, and outputs final metrics (`[SUMMARY]`).

## Supporting Assets & Workflows
- **`cv.md`**: Candidate resume in Markdown consumed by Gemini for fit-score evaluation and personalized copywriting.
- **`cv.pdf`**: Physical PDF resume attached to every Gmail draft.
- **`requirements.txt`**: Python dependencies (`google-genai`, `requests`, `ddgs`).
- **`.github/workflows/daily.job.yml`**: GitHub Actions workflow (`ubuntu-latest`, Python 3.12, pip cache).
- **`.antigravity/context_loader.md`**: Initial V1 architectural specification in Spanish.

---

# 3. Environment Variables & Secrets Contract
| Variable | Purpose |
| :--- | :--- |
| `GEMINI_API_KEY` | Google AI Studio API key for Gemini REST API calls |
| `SMTP_USER` | Gmail address used for IMAP authentication, `From` header, and self-addressed LinkedIn DM drafts |
| `SMTP_APP_PASSWORD` | 16-character Google App Password for IMAP SSL login on port 993 |

---

# 4. Traceability Log Tags Contract
| Tag | Stage |
| :--- | :--- |
| `[INIT]` | Environment & credential initialization check |
| `[CV]` | `cv.md` profile loading & character count |
| `[OSINT]` / `[OSINT #N]` | DuckDuckGo dork query, scraped LinkedIn URL, extracted email, and full snippet |
| `[EVAL i/N]` | Start of job post evaluation |
| `[GEMINI]` | Model name, attempt number, HTTP status, latency (s), `fit_score`, and `subject` (or full HTTP error) |
| `[DECISION i/N]` | `ACCEPTED` / `DISCARDED`, outreach mode (`COLD_EMAIL` / `LINKEDIN_DM`), target email, and generated body |
| `[MIME]` | PDF attachment verification and size in KB |
| `[IMAP]` | Target Gmail Drafts folder, IMAP APPEND status, sender, recipient, and subject |
| `[SUMMARY]` | End-of-run totals (`total_evaluated`, `drafts_saved`, `discarded`) |

---

# 5. Context Synthesis Protocol (Instructions for the Agent)
Whenever a major iteration is completed in `aGeminiAgentJobSeeker`:
1. Read this file first before scanning the repository to save context tokens.
2. If new methods, environment variables, log tags, or workflow steps are added, update Sections **2**, **3**, and **4**.
3. Append a concise entry under **Section 6 (Iteration Log)** summarizing the date, objective, modified files, and verification status.

---

# 6. Iteration Log
- **Iteration 1 (V1 Autonomous OSINT & IMAP Draft Engine):** Implemented `JobSeekerAgent` in `agent.py` with DuckDuckGo OSINT dorking (`ddgs`), direct Gemini REST API calls with cascading model fallback (`gemini-3.8-flash` -> `gemini-3.8-flash-8b` -> static fallback), MIME PDF attachment (`cv.pdf`), and Gmail IMAP SSL draft creation (`daily.job.yml`).
- **Iteration 2 (English Code Comments, End-to-End Traceability & Documentation):** Standardized all code comments and docstrings in `agent.py` and `daily.job.yml` to English, implemented non-redundant stage-based traceability logs (`[INIT]`, `[CV]`, `[OSINT]`, `[EVAL]`, `[GEMINI]`, `[DECISION]`, `[MIME]`, `[IMAP]`, `[SUMMARY]`), authored comprehensive UTF-8 `README.md`, and created `.antigravity/context-synthesizer.md`.

