import json
import logging
import sys
from pathlib import Path
from typing import Dict, Any
from datetime import datetime
import uuid
import boto3

# Add shared utilities to path
sys.path.append(str(Path(__file__).parent.parent.parent / "shared"))
import config

logger = logging.getLogger()
logger.setLevel(config.LOG_LEVEL)

dynamodb = boto3.resource('dynamodb')


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    try:
        logger.info("Saving application to DynamoDB")
        
        # Get table
        table_name = config.DYNAMODB_TABLE
        table = dynamodb.Table(table_name)
        
        # Generate unique application ID
        application_id = str(uuid.uuid4())
        timestamp = datetime.utcnow().isoformat()
        
        # Extract user_id
        user_id = event.get("user_id", "anonymous")
        
        # Build application item
        application_item = {
            "user_id": user_id,  
            "application_id": application_id, 
            
            "created_at": timestamp,
            "updated_at": timestamp,
            "status": "draft",

            # Job details
            "job_title": event.get("job_title", ""),
            "company_name": event.get("company_name", ""),
            "job_description": event.get("job_description", ""),
            "job_url": event.get("job_url", ""),
            
            # outputs (store as JSON strings for DynamoDB)
            "job_analysis": json.dumps(event.get("job_analysis", {})),
            "tailored_resume": json.dumps(event.get("tailored_resume", {})),
            "cover_letter": json.dumps(event.get("cover_letter", {})),
            "interview_prep": json.dumps(event.get("interview_prep", {})),
            
            # Metadata
            "resume_text_length": len(event.get("resume_text", "")),
        }
        
        # Optional fields
        if "applied_date" in event:
            application_item["applied_date"] = event["applied_date"]
        
        if "notes" in event:
            application_item["notes"] = event["notes"]
        
        logger.info(f"Saving application {application_id} for user {user_id}")
        
        # Save to DynamoDB
        table.put_item(Item=application_item)
        
        logger.info(f"Application saved successfully: {application_id}")
        
        return {
            "statusCode": 200,
            "application_id": application_id,
            "user_id": user_id,
            "saved_at": timestamp,
            "table_name": table_name
        }
        
    except Exception as e:
        logger.error(f"Failed to save application: {str(e)}", exc_info=True)
        return {
            "statusCode": 500,
            "error": str(e),
            "error_type": type(e).__name__
        }


def get_application(user_id: str, application_id: str) -> Dict[str, Any]:
    """
    Retrieve a saved application
    
    Args:
        user_id: User identifier
        application_id: Application UUID
        
    Returns:
        Application data or None
    """
    try:
        table_name = config.DYNAMODB_TABLE
        table = dynamodb.Table(table_name)
        
        response = table.get_item(
            Key={
                "user_id": user_id,
                "application_id": application_id
            }
        )
        
        if "Item" not in response:
            return None
        
        item = response["Item"]
        
        if "job_analysis" in item:
            item["job_analysis"] = json.loads(item["job_analysis"])
        if "tailored_resume" in item:
            item["tailored_resume"] = json.loads(item["tailored_resume"])
        if "cover_letter" in item:
            item["cover_letter"] = json.loads(item["cover_letter"])
        if "interview_prep" in item:
            item["interview_prep"] = json.loads(item["interview_prep"])
        
        return item
        
    except Exception as e:
        logger.error(f"Failed to retrieve application: {str(e)}")
        return None


def list_applications(user_id: str, limit: int = 10) -> list:
    """
    List all applications for a user
    
    Args:
        user_id: User identifier
        limit: Maximum number of applications to return
        
    Returns:
        List of applications
    """
    try:
        table_name = config.DYNAMODB_TABLE
        table = dynamodb.Table(table_name)
        
        response = table.query(
            KeyConditionExpression="user_id = :uid",
            ExpressionAttributeValues={":uid": user_id},
            Limit=limit,
            ScanIndexForward=False  # Most recent first
        )
        
        return response.get("Items", [])
        
    except Exception as e:
        logger.error(f"Failed to list applications: {str(e)}")
        return []