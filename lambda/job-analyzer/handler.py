"""
Job Analyzer -Agent 1-
Extract structured requirements from job descriptions using AWS Bedrock
"""

import json
import logging
import sys
from pathlib import Path
from typing import Dict,Any

# Adding shared utilities to path
sys.path.append(str(Path(__file__).parent.parent.parent / "shared"))

from bedrock_client import BedrockClient
from prompts import PromptTemplates
import config

logger=logging.getLogger()
logger.setLevel(config.LOG_LEVEL)

def lambda_handler(event:Dict[str,Any],context:Any)->Dict[str,Any]:
    try:
        logger.info(f"Received event: {json.dumps(event,default=str)}")
        # Input validation
        required_fields=["job_description","job_title","company_name"]
        for field in required_fields:
            if field not in event:
                raise ValueError(f"Missing required field: {field}")
        job_description=event["job_description"]
        job_title=event["job_title"]
        company_name=event["company_name"]

        if not job_description.strip():
            raise ValueError(f"job_description cannot be empty")
        
        logger.info(f"Analyzing job: {job_title} at {company_name}")
        logger.info(f"Job description length: {len(job_description)} charachters")

        # Initialize Bedrock client with Amazon Nova lite
        model_id=config.MODELS["job_analyzer"]
        logger.info(f"Using model: {model_id}")

        bedrock=BedrockClient(
            model_id=model_id,
            region=config.BEDROCK_REGION
        )

        # Generate propmt from templates
        prompt= PromptTemplates.job_analyzer(
            job_description=job_description,
            job_title=job_title,
            company_name=company_name
        )

        logger.info(f"Generated prompt, length: {len(prompt)} characters")

        # Call Bedrock
        logger.info("Invoking Bedrock...")
        response=bedrock.invoke(
            prompt=prompt,
            max_tokens=config.MAX_TOKENS,
            temperature=config.TEMPERATURE
        )

        logger.info(f"Bedrock response received: {response['usage']}")
        # Stop reason added if fails
        logger.info(f"Stop reason: {response.get('stop_reason', 'unknown')}")
        # Check if the response was complete
        if response.get('stop_reason') == 'max_tokens':
            logger.warning("Response was truncated due to max_tokens limit!")

        # Parse Json response
        response_text = response["content"].strip()

        # Remove markdown code block
        if response_text.startswith("```"):
            # Remove opening ```json or ``` 
            response_text = response_text.split("\n", 1)[1] if "\n" in response_text else response_text[3:]
            # Remove closing ```
            if response_text.endswith("```"):
                response_text = response_text.rsplit("```", 1)[0]
            response_text = response_text.strip()
        
        # Additional cleanup: remove any remaining markdown artifacts
        response_text = response_text.replace("```json", "").replace("```", "").strip()
        try:
            job_analysis=json.loads(response_text)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: { response_text[:500]}")
            raise ValueError(f"AI returned invaild JSON: {str(e)}")
        
        # Validate response 
        validate_job_analysis(job_analysis)

        # Calculate cost
        estimated_cost=bedrock.calculate_cost(
            input_tokens=response["usage"]["input_tokens"],
            output_tokens=response["usage"]["output_tokens"]
        )
        logger.info(f"Job analysis complete. Estimated cost: ${estimated_cost:.6f}")
        logger.info(f"Found {len(job_analysis.get('required_skills',[]))} required skills")

        return {
            "statusCode":200,
            "statusCode": 200,
            "job_analysis": job_analysis,
            "metadata": {
                "model_used": model_id,
                "tokens_used": response["usage"],
                "estimated_cost": estimated_cost,
                "prompt_length": len(prompt),
                "response_length": len(response_text)
            }
            
        }
    except Exception as e:
        logger.error(f"Job analysis failed: {str(e)}", exc_info=True)
        return {
            "statusCode": 500,
            "error": str(e),
            "error_type": type(e).__name__
        }
def validate_job_analysis(analysis: Dict[str, Any]) -> None:
    """
    Validate that job analysis has required structure
    
    Args:
        analysis: Parsed job analysis JSON
        
    Raises:
        ValueError: If structure is invalid
    """
    required_fields = [
        "required_skills",
        "preferred_skills",
        "key_responsibilities",
        "technical_tools",
        "soft_skills",
        "role_level"
    ]
    
    for field in required_fields:
        if field not in analysis:
            raise ValueError(f"Missing required field in job analysis: {field}")
    
    # Validate types
    list_fields = [
        "required_skills", "preferred_skills", "education_requirements",
        "key_responsibilities", "technical_tools", "soft_skills", "company_values"
    ]
    
    for field in list_fields:
        if field in analysis and not isinstance(analysis[field], list):
            raise ValueError(f"Field {field} must be a list, got {type(analysis[field])}")
    
    # Validate role_level is valid
    valid_levels = ["entry", "mid", "senior", "lead", "executive"]
    role_level = analysis.get("role_level", "").lower()
    if role_level not in valid_levels:
        logger.warning(f"Invalid role_level: {role_level}, defaulting to 'mid'")
        analysis["role_level"] = "mid"
    
    logger.info("Job analysis structure validated successfully")


# For local testing
if __name__ == "__main__":
    # Test event
    test_event = {
        "job_description": """
We are seeking a Cloud Solutions Architect with expertise in AWS serverless technologies. 

Responsibilities:
- Design and implement serverless architectures using AWS Lambda, API Gateway, and DynamoDB
- Build CI/CD pipelines using AWS CodePipeline and CloudFormation
- Collaborate with development teams to optimize cloud costs
- Ensure security best practices using IAM and VPC

Requirements:
- 3+ years of AWS experience
- Strong Python programming skills
- Experience with Infrastructure as Code (CloudFormation or Terraform)
- AWS Solutions Architect certification preferred
- Bachelor's degree in Computer Science or related field

Skills:
- AWS Lambda, S3, DynamoDB, API Gateway
- Python, Boto3
- CI/CD, DevOps practices
- Problem-solving and communication skills

We value innovation, ownership, and customer obsession.
        """,
        "job_title": "Cloud Solutions Architect",
        "company_name": "Tech Innovations Inc."
    }
    
    result = lambda_handler(test_event, None)
    print(json.dumps(result, indent=2))
