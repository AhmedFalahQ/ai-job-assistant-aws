"""
Interview Prep Lambda (Agent 4)
Generates interview questions with STAR-format answers
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
    Lambda handler for interview preparation
    
    Input event format:
    {
        "job_title": ,
        "company_name": ,
        "job_analysis": {...},  // From job-analyzer
        "candidate_experience": "Summary of relevant experience..."
    }
    
    Returns:
    {
        "statusCode": 200,
        "interview_prep": {
            "questions": [
                {
                    "question": "Tell me about...",
                    "type": "behavioral",
                    "answer_framework": {...},
                    "key_points_to_mention": [...]
                }
            ]
        },
        "metadata": {...}
    }
    """
    try:
        logger.info(f"Received event keys: {list(event.keys())}")
        
        # Validate input
        required_fields = ["job_title", "company_name", "job_analysis"]
        for field in required_fields:
            if field not in event:
                raise ValueError(f"Missing required field: {field}")
        
        job_title = event["job_title"]
        company_name = event["company_name"]
        job_analysis = event["job_analysis"]
        candidate_experience = event.get("candidate_experience", "Experienced professional in cloud and AWS")
        
        logger.info(f"Generating interview prep for {job_title} at {company_name}")
        
        # Initialize Bedrock client with Nova Lite
        model_id = config.MODELS["interview_prep"]
        logger.info(f"Using model: {model_id}")
        
        bedrock = BedrockClient(
            model_id=model_id,
            region=config.BEDROCK_REGION
        )
        
        # Generate prompt using template
        prompt = PromptTemplates.interview_prep(
            job_title=job_title,
            company_name=company_name,
            job_analysis=job_analysis,
            candidate_experience=candidate_experience
        )
        
        logger.info(f"Generated prompt, length: {len(prompt)} characters")
        
        # Call Bedrock
        logger.info("Invoking Bedrock...")
        response = bedrock.invoke(
            prompt=prompt,
            max_tokens=config.MAX_TOKENS,
            temperature=0.4  # Balanced for question generation
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
            interview_data = json.loads(response_text)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {response_text[:500]}")
            raise ValueError(f"AI returned invalid JSON: {str(e)}")
        
        # Validate response structure
        validate_interview_prep(interview_data)
        
        # Calculate cost
        estimated_cost = bedrock.calculate_cost(
            input_tokens=response["usage"]["input_tokens"],
            output_tokens=response["usage"]["output_tokens"]
        )
        
        logger.info(f"Interview prep complete. Cost: ${estimated_cost:.6f}")
        logger.info(f"Generated {len(interview_data.get('questions', []))} questions")
        
        return {
            "statusCode": 200,
            "interview_prep": interview_data,
            "metadata": {
                "model_used": model_id,
                "tokens_used": response["usage"],
                "estimated_cost": estimated_cost,
                "prompt_length": len(prompt),
                "response_length": len(response_text)
            }
        }
        
    except Exception as e:
        logger.error(f"Interview prep failed: {str(e)}", exc_info=True)
        return {
            "statusCode": 500,
            "error": str(e),
            "error_type": type(e).__name__
        }


def validate_interview_prep(prep: Dict[str, Any]) -> None:
    """Validate interview prep structure"""
    
    if "questions" not in prep:
        raise ValueError("Missing 'questions' field")
    
    if not isinstance(prep["questions"], list) or len(prep["questions"]) < 3:
        raise ValueError("Must have at least 3 questions")
    
    for q in prep["questions"]:
        if "question" not in q or "type" not in q or "answer_framework" not in q:
            raise ValueError("Each question must have question, type, and answer_framework")
    
    logger.info("Interview prep structure validated successfully")