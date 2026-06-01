# Adeed — AI Job Application Assistant

A serverless, agent-based job application assistant built on AWS. The system analyzes job descriptions, tailors resume content, generates cover letters, and prepares interview questions — all from a single PDF upload.

**Live demo:** https://adeed.ahmedfalah.dev

---

## Overview

Adeed (عضيد — Arabic for assistant) automates the most time-consuming parts of job application preparation. The user provides a job description and resume; the system returns a complete application package within 30–45 seconds.

The project demonstrates end-to-end AI system design using AWS-native services: multi-agent orchestration, cost-optimized model selection, serverless infrastructure, and a production frontend deployed on CloudFront.

**Built by:** Ahmed Falah Alqahtani — AWS Certified Solutions Architect  
**LinkedIn:** [ahmed-alqahtani-afq](https://linkedin.com/in/ahmed-alqahtani-afq)

---

## Features

- Resume tailoring — rewrites experience bullets to match job requirements and ATS keywords
- Cover letter generation — personalized letter based on candidate background and job analysis
- Interview preparation — generates STAR-format questions with answer frameworks
- Job analysis — extracts required skills, tools, responsibilities, and role level
- LinkedIn import — paste a job URL to auto-fill the form via async scraping
- PDF resume upload — server-side parsing using pdfplumber for accurate text extraction

---

## Architecture

```
https://adeed.ahmedfalah.dev
          |
    CloudFront (CDN + HTTPS)
          |
     S3 Static Site
          |
     API Gateway (REST)
     |              |
  /generate     /scrape-job
     |              |
Step Functions   Async Scraper
  (Express)      (Playwright)
     |
  6 Lambda Agents
     |
  AWS Bedrock
  - Amazon Nova Lite  (job analysis, interview prep)
  - Claude Haiku 4.5  (resume tailoring, cover letter)
     |
  DynamoDB + S3
```

### Step Functions Workflow

```
ParseResume
    |
AnalyzeJob
    |
    +-- TailorResume ------+
    +-- GenerateCoverLetter-+-- MergeResults -- SaveApplication -- Success
    +-- PrepareInterview ---+
```

The three generation agents run in parallel, reducing total execution time.

---

## Lambda Agents

| Agent | Model | Responsibility |
|---|---|---|
| pdf-parser | Nova Lite | Extract resume text from PDF, generate candidate background summary |
| job-analyzer | Nova Lite | Extract structured requirements from job description |
| resume-tailor | Claude Haiku 4.5 | Rewrite experience bullets for ATS alignment |
| coverletter-generator | Claude Haiku 4.5 | Write personalized cover letter |
| interview-prep | Nova Lite | Generate STAR-format interview questions |
| app-saver | — | Persist application package to DynamoDB |

---

## Tech Stack

**AWS Services**  
Bedrock, Lambda, Step Functions (Express), API Gateway, S3, DynamoDB, CloudFront, ACM, Route 53, IAM, CloudWatch, ECR

**AI Models**  
Amazon Nova Lite v2, Anthropic Claude Haiku 4.5 — selected for cost efficiency at ~$0.02 per application

**Backend**  
Python 3.11, Boto3, pdfplumber, PyPDF2, Playwright (container Lambda)

**Frontend**  
HTML, CSS, JavaScript — single file, no framework, deployed to S3

---

## Project Structure

```
adeed/
├── shared/
│   ├── bedrock_client.py       # Unified Bedrock API wrapper
│   ├── config.py               # Model IDs and environment config
│   └── prompts.py              # All AI prompt templates
├── lambda/
│   ├── pdf-parser/
│   ├── job-analyzer/
│   ├── resume-tailor/
│   ├── coverletter-generator/
│   ├── interview-prep/
│   ├── app-saver/
│   ├── presigned-url-generator/
│   ├── job-scraper-start/
│   ├── job-scraper-fetch/
│   └── job-scraper-worker/
└── frontend/
    ├── adeed.html
    └── TYAI_Logo_Main.svg
```

---

## Cost Model

Target: under $15 per month at moderate usage.

| Service | Estimated Monthly Cost |
|---|---|
| AWS Bedrock (Nova Lite + Haiku 4.5) | $0.40 – $1.00 |
| Lambda | $0.10 |
| Step Functions | $0.20 |
| API Gateway | $0.50 |
| S3 + CloudFront | $0.10 |
| DynamoDB | $0.00 (free tier) |
| Route 53 | $0.50 |
| **Total** | **~$1.80 – $2.50 / month** |

Cost per application: approximately $0.02.

---

## Key Design Decisions

**Express over Standard Step Functions**  
StartSyncExecution requires Express type to return results synchronously through API Gateway within a single HTTP response.

**Backend PDF parsing over client-side**  
PDF.js (browser-based) struggles with complex resume layouts, symbols, and multi-column formatting. Routing uploads through S3 and parsing server-side with pdfplumber produces significantly more accurate text extraction.

**Model selection by task type**  
Nova Lite handles structured extraction tasks (job analysis, interview questions) at lower cost. Claude Haiku 4.5 handles open-ended writing tasks (resume tailoring, cover letters) where quality matters more.

**candidate_background auto-generated**  
Rather than asking users to describe themselves, pdf-parser generates a 2–3 sentence professional summary from the resume using Nova Lite. This removes a form field without losing context for downstream agents.

**Async polling for LinkedIn scraper**  
API Gateway enforces a 29-second maximum timeout. Playwright-based scraping takes 35–45 seconds. The solution fires the scraper Lambda asynchronously, stores the result in DynamoDB, and polls from the frontend every 3 seconds.

---

## Setup

Prerequisites: AWS account with Bedrock model access enabled, AWS CLI configured, Python 3.11, Docker (for the scraper container).

Deployment is manual — each Lambda is packaged and deployed individually. The shared utilities folder must be included in each Lambda deployment package.

```bash
# Package a Lambda with shared utilities
cd lambda/job-analyzer
pip install -r requirements.txt -t .
cp -r ../../shared/* .
zip -r ../../deployment-packages/job-analyzer.zip .
```

The LinkedIn scraper runs as a container Lambda. Build and push to ECR:

```bash
cd lambda/job-scraper-worker
docker build --platform linux/amd64 --provenance=false -t job-scraper .
docker tag job-scraper:latest ACCOUNT_ID.dkr.ecr.REGION.amazonaws.com/job-scraper:latest
docker push ACCOUNT_ID.dkr.ecr.REGION.amazonaws.com/job-scraper:latest
```

Environment variables are managed through Lambda configuration — no `.env` files are used.

---

## Security

- IAM roles follow least-privilege principle — each Lambda has only the permissions it needs
- No AWS credentials are exposed to the frontend
- PDF uploads go directly from the browser to S3 via presigned URLs — the backend never handles the binary file over API Gateway
- CORS is restricted to the production domain
- All data in transit uses HTTPS; S3 storage uses server-side encryption

---

## Roadmap

- Arabic language support with RTL frontend
- User authentication via Amazon Cognito
- Application history and resume versioning
- WAF rate limiting on API Gateway
- CloudWatch monitoring dashboards and cost alarms

---

## License

MIT License — see LICENSE file for details.
