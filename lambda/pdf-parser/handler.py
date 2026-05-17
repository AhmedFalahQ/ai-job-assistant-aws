import json
import logging
import sys
from pathlib import Path
from io import BytesIO
from typing import Dict, Any

import boto3

sys.path.append(str(Path(__file__).parent.parent.parent / "shared"))
from bedrock_client import BedrockClient
import config

try:
    import PyPDF2
except ImportError:
    PyPDF2 = None

try:
    import pdfplumber
except ImportError:
    pdfplumber = None

logger = logging.getLogger()
logger.setLevel(config.LOG_LEVEL)

s3_client = boto3.client('s3')


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Handler for PDF parsing + background generation.

    
    {
        "statusCode": 200,
        "resume_text": "Full resume text...",
        "candidate_background": "2-3 sentence professional summary...",
        "page_count": 2,
        "char_count": 1234,
        "parsing_method": "PyPDF2 | pdfplumber | provided"
    }
    """
    try:
        logger.info(f"Received event keys: {list(event.keys())}")

        # Get resume text
        if event.get("resume_text"):
            logger.info("Resume text provided directly, skipping PDF parsing")
            resume_text    = event["resume_text"]
            page_count     = None
            parsing_method = "provided"

        else:
            s3_bucket = event.get("s3_bucket")
            s3_key    = event.get("s3_key")

            if not s3_bucket or not s3_key:
                raise ValueError("Must provide either 'resume_text' or 's3_bucket'/'s3_key'")

            logger.info(f"Downloading PDF from s3://{s3_bucket}/{s3_key}")
            pdf_obj     = s3_client.get_object(Bucket=s3_bucket, Key=s3_key)
            pdf_content = pdf_obj['Body'].read()
            logger.info(f"Downloaded {len(pdf_content)} bytes")

            resume_text, page_count, parsing_method = parse_pdf(pdf_content)

            if not resume_text or len(resume_text.strip()) < 50:
                raise ValueError("Failed to extract meaningful text from PDF")

            logger.info(f"Extracted {len(resume_text)} characters using {parsing_method}")

        # Generate candidate background summary
        logger.info("Generating candidate background summary via Bedrock...")
        candidate_background = generate_background(resume_text)
        logger.info(f"Background generated: {candidate_background[:100]}...")

        return {
            "statusCode":           200,
            "resume_text":          resume_text,
            "candidate_background": candidate_background,
            "page_count":           page_count,
            "char_count":           len(resume_text),
            "parsing_method":       parsing_method
        }

    except Exception as e:
        logger.error(f"PDF parsing failed: {str(e)}", exc_info=True)
        return {
            "statusCode": 500,
            "error":      str(e),
            "error_type": type(e).__name__
        }


def generate_background(resume_text: str) -> str:
    """
    Uses Bedrock Nova Lite to extract a concise 2-3 sentence
    professional background summary from the resume text.
    Falls back to a generic placeholder if Bedrock fails.
    """
    try:
        # Truncate resume to first 3000 chars for enough context, saves tokens
        truncated = resume_text[:3000]

        prompt = f"""You are a professional resume analyst. Read the resume below and write a concise 2-3 sentence professional background summary.

RULES:
- Write in third person (e.g. "Experienced software engineer with...")
- Mention years of experience if stated
- Highlight the top 2-3 skills or domains
- Keep it under 60 words
- Return ONLY the summary text, no labels, no JSON, no explanation

RESUME:
{truncated}

SUMMARY:"""

        bedrock = BedrockClient(
            model_id=config.MODELS["job_analyzer"],  # Nova Lite
            region=config.BEDROCK_REGION
        )

        response = bedrock.invoke(
            prompt=prompt,
            max_tokens=150,
            temperature=0.2
        )

        summary = response["content"].strip()

        # Sanity check if model returns something weird, fall back
        if len(summary) < 20 or len(summary) > 500:
            raise ValueError(f"Unexpected summary length: {len(summary)}")

        logger.info(f"Background summary tokens used: {response['usage']}")
        return summary

    except Exception as e:
        logger.warning(f"Background generation failed, using fallback: {str(e)}")
        return "Experienced professional with a background in their field, seeking new opportunities."


def parse_pdf(pdf_content: bytes) -> tuple[str, int, str]:
    if PyPDF2:
        try:
            text, pages = parse_with_pypdf2(pdf_content)
            if text and len(text.strip()) > 50:
                return text, pages, "PyPDF2"
        except Exception as e:
            logger.warning(f"PyPDF2 failed: {str(e)}")

    if pdfplumber:
        try:
            text, pages = parse_with_pdfplumber(pdf_content)
            if text and len(text.strip()) > 50:
                return text, pages, "pdfplumber"
        except Exception as e:
            logger.warning(f"pdfplumber failed: {str(e)}")

    raise ValueError("All PDF parsing methods failed")


def parse_with_pypdf2(pdf_content: bytes) -> tuple[str, int]:
    pdf_file   = BytesIO(pdf_content)
    pdf_reader = PyPDF2.PdfReader(pdf_file)
    text_parts = []
    page_count = len(pdf_reader.pages)

    for page_num in range(page_count):
        text = pdf_reader.pages[page_num].extract_text()
        if text:
            text_parts.append(text)

    return clean_text("\n\n".join(text_parts)), page_count


def parse_with_pdfplumber(pdf_content: bytes) -> tuple[str, int]:
    pdf_file   = BytesIO(pdf_content)
    text_parts = []
    page_count = 0

    with pdfplumber.open(pdf_file) as pdf:
        page_count = len(pdf.pages)
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                text_parts.append(text)

    return clean_text("\n\n".join(text_parts)), page_count


def clean_text(text: str) -> str:
    lines   = [line.strip() for line in text.split('\n')]
    lines   = [line for line in lines if line]
    cleaned = '\n'.join(lines)
    cleaned = cleaned.encode('ascii', 'ignore').decode('ascii')
    return cleaned
