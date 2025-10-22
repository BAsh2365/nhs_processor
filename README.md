NHS Medical Document Processor for Cardiovascular Issues (NHS - DPCI) - Modularized Demo (MVP) Note: I am NOT affiliated with the NHS. This is just a project I have made using online, open-source PDFs and Guidelines from the NHS and NICE. 

This workspace contains an MVP version of the NHS medical document processor demo. AI-code assisted project with Github Copilot (By Bhargav Ashok, used GPT 5 in VS Code IDE for this project). Still a Work in Progress. It is NOT a full-fledged finished Product. It is a Personal Interest Project.


This AI tool is designed to assist cardiovascular surgeons within the NHS in the triage of referral letters received from GPs. These letters, often numbering in the hundreds or thousands, contain detailed patient histories and descriptions of current medical concerns. Traditionally, reviewing and prioritizing these referrals is a time-consuming task, often rotated among surgical teams.

The AI model streamlines this process by summarizing key patient information and highlighting critical issues and a suggested plan of action, enabling surgeons to quickly identify cases that require urgent attention or further investigation, including potential surgery. While a human-in-the-loop remains essential for final decision-making, this tool significantly reduces the time spent reviewing referrals and enhances clinical efficiency by focusing attention on the most relevant data.

Structure:
- backend/: core processing modules (anonymizer, pdf parsing, risk assessor, recommendation engine, processor)
- frontend/: Flask app and template for uploading PDFs

Privacy & Compliance
- PII is redacted before any analysis and files are deleted after processing.
- Patient identifiers are hashed using SHA-256 and only the hash is logged.
- Audit logs contain only the hashed patient id.
- AI Model's Knowledge base stems from NHS and NICE documentation.

# Create venv and install
python -m venv .venv; pip install -r requirements.txt

# You should have the following

- Claude API key
- env configurations set for transformers if needed
- env configurations for OCR PDF reading (Tesseract)
- Every library in the requirements.txt file

# Run frontend demo
python frontend\app.py 


# Tech stack

- Claude Opus API
- Python (adhering to DTAC NHS guidelines, model context, patient data types (usually strings), NLP, RAG, Tranformers, etc).
- OCR/PDF storage (RAG again) with ChromaDB Vector Database (with an open source embedding model)
- Flask app for API route handling
- Simple HTML front end

use of github copilot (GPT 5 mini)

# Future Improvements

- Graph/SQL Database usage (for flexible storage and debugging)

- Larger Context Window, Temperature adjustment (randomness/creativity/nuance), for more accurate information

- Accuracy in recommendation with more specified guidelines instead of three simple levels

- Human-in-the-loop frameworks, tests, etc..

# Ideal setup

- Scaling deployment aspects (following DTAC rules with a Cloud setup on AWS, GC or Azure).

- Data Engineering Pipeline with large-scale data and tools like databricks, spark, etc. (potentially from an NHS NLP dataset: https://github.com/nhsx/language-corpus-tools)

- Needs to be containerized and scaled with docker so that each user has their own instance. 

- System design flushed out with a GitHub CI/CD pipeline, tests, etc.


# Guidelines 

https://nhsdigital.github.io/rap-community-of-practice/introduction_to_RAP/levels_of_RAP/

https://github.com/nhsx/open-source-policy/blob/main/open-source-policy.md#b-readmes

- Estimated RAP Level: Around Baseline (Hobby Project with public data/PDFs available on the internet).

- Completion date for a "finished product" is undecided as it is a hobby project.


**If you have any questions about this project, let me know! (Email: Bhargav.ashok2023@gmail.com)**

**If you use this project please build upon it for the greater good of its original intent. Feel free to work on this project, clone it, approve it, etc. Please cite the author of this Repo when doing so (Bhargav Ashok)**





