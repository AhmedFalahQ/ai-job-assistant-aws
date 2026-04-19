"""
Cover Letter Generator Lambda (Agent 3)
Generates personalized cover letters using AWS Bedrock
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
    Lambda handler for cover letter generation
    
    Input event format:
    {
        "candidate_name": ,
        "candidate_background": ,
        "job_title": ,
        "company_name": ,
        "job_analysis": {...},  // From job-analyzer
        "tailored_experience": {...}  // From resume-tailor
    }
    
    Returns:
    {
        "statusCode": 200,
        "cover_letter": {
            "cover_letter": "Full letter text...",
            "key_points_covered": ["point1", "point2"],
            "word_count": 287
        },
        "metadata": {...}
    }
    """
    try:
        logger.info(f"Received event keys: {list(event.keys())}")
        
        # Validate input
        required_fields = ["candidate_name", "job_title", "company_name", "job_analysis", "tailored_experience"]
        for field in required_fields:
            if field not in event:
                raise ValueError(f"Missing required field: {field}")
        
        candidate_name = event["candidate_name"]
        candidate_background = event.get("candidate_background", "Experienced professional")
        job_title = event["job_title"]
        company_name = event["company_name"]
        job_analysis = event["job_analysis"]
        tailored_experience = event["tailored_experience"]
        
        logger.info(f"Generating cover letter for {candidate_name} applying to {job_title} at {company_name}")
        
        # Initialize Bedrock client with claude haiku
        model_id = config.MODELS["coverletter_generator"]
        logger.info(f"Using model: {model_id}")
        
        bedrock = BedrockClient(
            model_id=model_id,
            region=config.BEDROCK_REGION
        )
        
        # Generate prompt using template
        prompt = PromptTemplates.cover_letter(
            candidate_name=candidate_name,
            candidate_background=candidate_background,
            job_title=job_title,
            company_name=company_name,
            job_analysis=job_analysis,
            tailored_experience=tailored_experience
        )
        
        logger.info(f"Generated prompt, length: {len(prompt)} characters")
        
        # Call Bedrock
        logger.info("Invoking Bedrock...")
        response = bedrock.invoke(
            prompt=prompt,
            max_tokens=config.MAX_TOKENS,
            temperature=0.5  # Slightly higher for more natural writing
        )
        
        logger.info(f"Bedrock response received: {response['usage']}")
        logger.info(f"Stop reason: {response.get('stop_reason', 'unknown')}")
        
        # Parse JSON response
        response_text = response["content"].strip()
        
        # Remove markdown code blocks if present
        if response_text.startswith("```"):
            response_text = response_text.split("\n", 1)[1] if "\n" in response_text else response_text[3:]
            if response_text.endswith("```"):
                response_text = response_text.rsplit("```", 1)[0]
            response_text = response_text.strip()
        
        response_text = response_text.replace("```json", "").replace("```", "").strip()
        
        try:
            cover_letter_data = json.loads(response_text)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {response_text[:500]}")
            raise ValueError(f"AI returned invalid JSON: {str(e)}")
        
        # Validate response structure
        validate_cover_letter(cover_letter_data)
        
        # Calculate cost
        estimated_cost = bedrock.calculate_cost(
            input_tokens=response["usage"]["input_tokens"],
            output_tokens=response["usage"]["output_tokens"]
        )
        
        logger.info(f"Cover letter generation complete. Cost: ${estimated_cost:.6f}")
        logger.info(f"Word count: {cover_letter_data.get('word_count')}")
        
        return {
            "statusCode": 200,
            "cover_letter": cover_letter_data,
            "metadata": {
                "model_used": model_id,
                "tokens_used": response["usage"],
                "estimated_cost": estimated_cost,
                "prompt_length": len(prompt),
                "response_length": len(response_text)
            }
        }
        
    except Exception as e:
        logger.error(f"Cover letter generation failed: {str(e)}", exc_info=True)
        return {
            "statusCode": 500,
            "error": str(e),
            "error_type": type(e).__name__
        }


def validate_cover_letter(letter: Dict[str, Any]) -> None:
    """Validate cover letter structure"""
    
    required_fields = ["cover_letter", "key_points_covered", "word_count"]
    
    for field in required_fields:
        if field not in letter:
            raise ValueError(f"Missing required field: {field}")
    
    if not isinstance(letter["cover_letter"], str) or len(letter["cover_letter"]) < 100:
        raise ValueError("Cover letter text too short or invalid")
    
    if not isinstance(letter["key_points_covered"], list):
        raise ValueError("key_points_covered must be a list")
    
    logger.info("Cover letter structure validated successfully")