"""
Resume Tailor Lambda (Agent 2)
Rewrites resume experience to match job requirements using AWS Bedrock
"""

import json
import logging
import sys
from pathlib import Path
from typing import Dict, Any

# Add shared utilities to path
sys.path.append(str(Path(__file__).parent.parent.parent / "shared"))

from bedrock_client import BedrockClient
from prompts import PromptTemplates
import config

# Configure logging
logger = logging.getLogger()
logger.setLevel(config.LOG_LEVEL)


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda handler for resume tailoring
    
    Input event format:
    {
        "resume_text": "Full resume text from pdf-parser...",
        "job_analysis": {...},  // Output from job-analyzer
        "job_title": str,
        "company_name": str
    }
    
    Returns:
    {
        "statusCode": 200,
        "tailored_resume": {
            "tailored_experience": [
                {
                    "company": "Company Name", // Examples
                    "title": "Job Title",
                    "dates": "Jun 2023 - Aug 2023",
                    "bullets": ["bullet1", "bullet2", ...]
                }
            ],
            "keywords_added": ["keyword1", "keyword2"],
            "relevance_score": 85
        },
        "metadata": {
            "model_used": "anthropic.claude-3-5-haiku-20241022-v1:0",
            "tokens_used": {...},
            "estimated_cost": 0.015
        }
    }
    """
    try:
        logger.info(f"Received event keys: {list(event.keys())}")
        
        # Validate input
        required_fields = ["resume_text", "job_analysis", "job_title", "company_name"]
        for field in required_fields:
            if field not in event:
                raise ValueError(f"Missing required field: {field}")
        
        resume_text = event["resume_text"]
        job_analysis = event["job_analysis"]
        job_title = event["job_title"]
        company_name = event["company_name"]
        
        logger.info(f"Tailoring resume for: {job_title} at {company_name}")
        logger.info(f"Resume length: {len(resume_text)} characters")
        logger.info(f"Job analysis has {len(job_analysis.get('required_skills', []))} required skills")
        
        # Initialize Bedrock client with Haiku 4.5
        model_id = config.MODELS["resume_tailor"]
        logger.info(f"Using model: {model_id}")
        
        bedrock = BedrockClient(
            model_id=model_id,
            region=config.BEDROCK_REGION
        )
        
        # Generate prompt using template
        prompt = PromptTemplates.resume_tailor(
            original_resume=resume_text,
            job_analysis=job_analysis,
            job_title=job_title,
            company_name=company_name
        )
        
        logger.info(f"Generated prompt, length: {len(prompt)} characters")
        
        # Call Bedrock
        logger.info("Invoking Bedrock...")
        response = bedrock.invoke(
            prompt=prompt,
            max_tokens=config.MAX_TOKENS,
            temperature=config.TEMPERATURE
        )
        
        logger.info(f"Bedrock response received: {response['usage']}")
        logger.info(f"Stop reason: {response.get('stop_reason', 'unknown')}")
        
        # Check if response was complete
        if response.get('stop_reason') == 'max_tokens':
            logger.warning("Response was truncated due to max_tokens limit!")
        
        # Parse JSON response
        response_text = response["content"].strip()
        
        # Remove markdown code blocks if present
        if response_text.startswith("```"):
            response_text = response_text.split("\n", 1)[1] if "\n" in response_text else response_text[3:]
            if response_text.endswith("```"):
                response_text = response_text.rsplit("```", 1)[0]
            response_text = response_text.strip()
        
        # Additional cleanup
        response_text = response_text.replace("```json", "").replace("```", "").strip()
        
        try:
            tailored_resume = json.loads(response_text)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {response_text[:500]}")
            raise ValueError(f"AI returned invalid JSON: {str(e)}")
        
        # Validate response structure
        validate_tailored_resume(tailored_resume)
        
        # Calculate cost
        estimated_cost = bedrock.calculate_cost(
            input_tokens=response["usage"]["input_tokens"],
            output_tokens=response["usage"]["output_tokens"]
        )
        
        logger.info(f"Resume tailoring complete. Estimated cost: ${estimated_cost:.6f}")
        logger.info(f"Relevance score: {tailored_resume.get('relevance_score', 'N/A')}")
        
        return {
            "statusCode": 200,
            "tailored_resume": tailored_resume,
            "metadata": {
                "model_used": model_id,
                "tokens_used": response["usage"],
                "estimated_cost": estimated_cost,
                "prompt_length": len(prompt),
                "response_length": len(response_text)
            }
        }
        
    except Exception as e:
        logger.error(f"Resume tailoring failed: {str(e)}", exc_info=True)
        return {
            "statusCode": 500,
            "error": str(e),
            "error_type": type(e).__name__
        }


def validate_tailored_resume(resume: Dict[str, Any]) -> None:
    
    required_fields = ["tailored_experience", "keywords_added", "relevance_score"]
    
    for field in required_fields:
        if field not in resume:
            raise ValueError(f"Missing required field in tailored resume: {field}")
    
    # Validate tailored_experience is list
    if not isinstance(resume["tailored_experience"], list):
        raise ValueError("tailored_experience must be a list")
    
    # Validate each experience entry
    for exp in resume["tailored_experience"]:
        if not isinstance(exp, dict):
            raise ValueError("Each experience entry must be a dict")
        if "bullets" not in exp or not isinstance(exp["bullets"], list):
            raise ValueError("Each experience must have 'bullets' as a list")
    
    # Validate relevance_score
    score = resume.get("relevance_score")
    if not isinstance(score, (int, float)) or score < 0 or score > 100:
        logger.warning(f"Invalid relevance_score: {score}, setting to 0")
        resume["relevance_score"] = 0
    
    logger.info("Tailored resume structure validated successfully")