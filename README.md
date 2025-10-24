NHS Medical Document Processor Framework for Cardiovascular Issues (NHS Personal Project/Framework  - DPCI) - Modularized Demo (MVP) 

**Note: I am NOT affiliated with the NHS. This is just a project I have made using online, open-source PDFs and Guidelines from the NHS and NICE. It is a framework for my thought process in how to use AI within Medical systems (considering ethical implications, technology guidelines, and other confounding factors). Results still need to be fine-tuned; it is NOT COMPLETE, it is NOT completely foolproof/tested, it is an unfinished idea/framework.**

This workspace contains an MVP version of the NHS medical document processor demo. AI-code assisted project with Github Copilot (By Bhargav Ashok, used GPT-5 mini and Claude 4.5 Sonnet in VS Code IDE + Claude Website for creation of project with iteration done by the codeowner). Still a Work in Progress. It is NOT a full-fledged finished Product. It is a Personal Interest Project/Framework as stated above. **There is no actual patient data used; only dummy data is used for testing**.


This AI tool is designed to assist cardiovascular surgeons within the NHS in the triage of referral letters received from GPs. These letters contain detailed patient histories and descriptions of current medical concerns. Traditionally, reviewing and prioritizing these referrals is a time-consuming task, often rotated among surgical teams. The NHS has to maintain a strict code of record management and practices when it comes to patients' data (records management guidelines found here: https://transform.england.nhs.uk/information-governance/guidance/records-management-code/records-management-code-of-practice/).

The AI model streamlines this process by summarizing key patient information and highlighting critical issues and a suggested plan of action (with three levels currently: Routine, Urgent, Emergency), enabling surgeons to quickly identify cases that require urgent attention or further investigation, including potential surgery. While a surgeon reviewing the information remains essential for final decision-making, this tool significantly reduces the time spent reviewing referrals and enhances clinical efficiency by focusing attention on the most relevant data.

Structure:
- backend/: core processing modules (anonymizer, pdf parsing, risk assessor, recommendation engine, processor)
- frontend/: Flask app and template for uploading PDFs

Privacy & Compliance:
- PII is redacted before any analysis, and patient files are deleted after processing.
- Patient identifiers are hashed using SHA-256. Only the hash is logged.
- Audit logs contain only the hashed patient ID (Not shown here, but will pop up once the project is running).
- AI Model's Knowledge base stems from NHS and NICE documentation.
- GitHub Workflows include Security Checks to combat any security issues with library vulnerabilities. 

# Create venv and install
python -m venv .venv; pip install -r requirements.txt

# You should have the following 

- BioGPT (by Microsoft: https://github.com/microsoft/BioGPT)
- env configurations set for transformers if needed
- env configurations for OCR PDF reading (Tesseract)
- Every library in the requirements.txt file

# Run frontend demo (Via VS Code CLI or similar)
Run python frontend\app.py OR similar 


# Tech stack

- BioGPT (by Microsoft: https://github.com/microsoft/BioGPT) + BART (https://huggingface.co/docs/transformers/en/model_doc/bart)
- Python (adhering to DTAC NHS guidelines, model context, patient data types (usually strings), NLP, RAG, Transformers, etc).
- OCR/PDF storage (RAG again) with ChromaDB Vector Database (with an open source embedding model) + txt files for testing
- Flask app for API route handling
- Simple HTML front end

use of github copilot (GPT 5 mini) + Claude 4.5 Sonnet

# Future Improvements

- Graph/SQL Database usage (for flexible storage and debugging)

- Larger Context Window, Temperature adjustment (randomness/creativity/nuance), for more accurate information

- Accuracy in recommendation with more specified guidelines instead of three simple levels

- Human-in-the-loop frameworks, more tests, etc.

# Ideal setup

- Scaling deployment aspects (following DTAC rules with a Cloud setup on AWS, GC, or Azure).

- Data Engineering Pipeline with large-scale data and tools like Databricks, Spark, etc. (potentially from an NHS NLP dataset: https://github.com/nhsx/language-corpus-tools)

- Needs to be containerized and scaled with Docker so that each user has their own instance. 

- System design flushed out with a GitHub CI/CD pipeline, tests, etc.


# Guidelines and extra Resources

https://nhsdigital.github.io/rap-community-of-practice/introduction_to_RAP/levels_of_RAP/

https://github.com/nhsx/open-source-policy/blob/main/open-source-policy.md#b-readmes

https://www.england.nhs.uk/long-read/artificial-intelligence-ai-and-machine-learning/

More info about NHS technology guidelines can be found online. This project adheres to those guidelines.

- Estimated RAP Level: Around Baseline (Hobby Project with public data/PDFs available on the internet).

- Completion date for a "finished product" is undecided, as it is a hobby project.


**If you have any questions about this framework project, let me know! (Email: Bhargav.ashok2023@gmail.com)**

**If you use this project, please build upon it for the greater good of its original intent. Feel free to work on this project, clone it, understand it, improve it, etc. Please cite the author of this Repo when doing so (Bhargav Ashok)**

Last edit: 10/24/2025




