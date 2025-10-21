NHS Medical Document Processor for Cardiovascular Issues (NHS - DPCI) - Modularized Demo (MVP)

This workspace contains an MVP version of the NHS medical document processor demo. AI-code assisted project with GIthub Copilot (By Bhargav Ashok, used GPT 5 in VS Code IDE for this project). Still a Work in Progress.

This AI tool is designed to assist cardiovascular surgeons within the NHS in the triage of referral letters received from GPs. These letters, often numbering in the hundreds or thousands, contain detailed patient histories and descriptions of current medical concerns. Traditionally, reviewing and prioritizing these referrals is a time-consuming task, often rotated among surgical teams.

The AI model streamlines this process by summarizing key patient information and highlighting critical issues and a suggested plan of action, enabling surgeons to quickly identify cases that require urgent attention or further investigation, including potential surgery. While a human-in-the-loop remains essential for final decision-making, this tool significantly reduces the time spent reviewing referrals and enhances clinical efficiency by focusing attention on the most relevant data.

Structure:
- backend/: core processing modules (anonymizer, pdf parsing, risk assessor, recommendation engine, processor)
- frontend/: Flask app and template for uploading PDFs

Privacy & Compliance
- PII is redacted before any analysis and files are deleted after processing.
- Patient identifiers are hashed using SHA-256 and only the hash is logged.
- Audit logs contain only the hashed patient id.

# Create virtualenv and install
python -m venv .venv; pip install -r requirements.txt

# You should have the following

- Claude API key
- env configurations set for transformers if needed
- env configurations for OCR PDF reading (Tesseract)

# Run frontend demo
python frontend\app.py


# Tech stack

Claude Opus API
Python (adhering to DTAC NHS guidelines, model context, patient data types (usually strings), etc).
OCR/PDF storage with ChromaDB Vector Database (with an open source embedding model)
Flask app for API routes
Simple HTML front end

use of github copilot (GPT 5 mini)

# Future Improvements

- Graph Database usage (for flexible storage and debugging)

- Larger Context Window for more accurate information

- Accuracy in diagnosis with more specified guidelines instead of three simple levels

- Human-in-the-loop nuance analysis based on patient history.


If you have any questions about this project, let me know! 


