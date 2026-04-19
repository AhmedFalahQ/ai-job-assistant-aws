import json
import logging
import boto3
from io import BytesIO
from typing import Dict,Any

try:
    import PyPDF2
except ImportError:
    PyPDF2=None

try:
    import pdfplumber
except ImportError:
    pdfplumber=None

logger=logging.getLogger()
logger.setLevel(logging.INFO)

s3_client=boto3.client('s3')

def lambda_handler(event:Dict[str,Any],context:Any)-> Dict[str,Any]:
    """
    A Handler for PDF parsing
    input format either taken from S3 or an already extracted text.

    returns:
    {
        "resume_text": "Extracted text from PDF",
        "page_count": 2,
        "char_count": 1234,
        "parsing_method": "PyPDF2|pdfplumber|provided"
    }
    """
    try:
        logger.info(f"Received event:{ json.dumps(event)}")

        if "resume_text" in event and event["resume_text"]:
            logger.info("Resume text provided, skipping PDF parsing")
            return{
                "statusCode":200,
                "resume_text":event["resume_text"],
                "page_count":None,
                "char_count":len(event["resume_text"]),
                "parsing_method":"provided"
            }
        
        s3_bucket=event.get("s3_bucket")
        s3_key=event.get("s3_key")

        if not s3_bucket or not s3_key:
            raise ValueError("Missing s3_bucket or s3_key in event")
        logger.info(f"Downloading PDF from s3://{s3_bucket}/{s3_key}")

        # Download PDF from S3
        pdf_obj=s3_client.get_object(Bucket=s3_bucket,Key=s3_key)
        pdf_content= pdf_obj['Body'].read()

        logger.info(f"Downloaded {len(pdf_content)} bytes")

        resume_text,page_count,method=parse_pdf(pdf_content)

        if not resume_text or len(resume_text.strip()) < 50:
            raise ValueError("Failed to extract meaningful text")
        
        logger.info(f"Extracted {len(resume_text)} charachters using {method}")

        return {
            "statusCode":200,
            "resume_text":resume_text,
            "page_count": page_count,
            "char_count":len(resume_text),
            "parsing_method":method
        }
    except Exception as e:
        logger.error(f"PDF parsing failed: {str(e)}",exc_info=True)
        return{
            "statusCode":500,
            "error":str(e),
            "error_type":type(e).__name__
        }
    
def parse_pdf(pdf_content:bytes)->tuple[str,int,str]:
    if PyPDF2:
        try:
            text,pages=parse_with_pypdf2(pdf_content)
            if text and len(text.strip()) > 50:
                return text,pages,"PyPDF2"
        except Exception as e:
            logger.warning(f"PyPDF2 parsing failed: {str(e)}")

    if pdfplumber:
        try:
            text,pages=parse_with_pdfplumber(pdf_content)
            if text and len(text.strip())> 50:
                return text,pages,"pdfplumber"
        except Exception as e:
            logger.warning(f"pdfplumber parsing failed: {str(e)}")
    raise ValueError("All PDF parsing methods failed")

def parse_with_pypdf2(pdf_content:bytes)->tuple[str,int]:
    pdf_file=BytesIO(pdf_content)
    pdf_reader=PyPDF2.PdfReader(pdf_file)

    text_parts=[]
    page_count=len(pdf_reader.pages)

    for page_num in range(page_count):
        page=pdf_reader.pages[page_num]
        text=page.extract_text()
        if text:
            text_parts.append(text)
    
    full_text="\n\n".join(text_parts)
    return clean_text(full_text),page_count

def parse_with_pdfplumber(pdf_content:bytes)->tuple[str,int]:
    pdf_file=BytesIO(pdf_content)
    text_parts=[]
    page_count=0

    with pdfplumber.open(pdf_file) as pdf:
        page_count=len(pdf.pages)
        for page in pdf.pages:
            text=page.extract_text()
            if text:
                text_parts.append(text)
    full_text="\n\n".join(text_parts)
    return clean_text(full_text),page_count

def clean_text(text:str)->str:
    # Remove excessive whitespaces
    lines=[line.strip() for line in text.split('\n') ]
    lines=[line for line in lines if line] # That will remove empty lines

    cleaned='\n'.join(lines)

    # Remove any weired unicode chars
    cleaned=cleaned.encode('ascii','ignore').decode('ascii')

    return cleaned