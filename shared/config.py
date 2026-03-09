"""
config file that contains model IDs and other settings
its purpose is to eliminate any code changes in Lambdas whenever decided to switch models
"""

import os

# AWS Bedrock models IDs
MODELS={
    "job_analyzer": os.environ.get(
        "JOB_ANALYZER_MODEL","us.amazon.nova-2-lite-v1:0"
    ),
    "resume_tailor": os.environ.get(
        "RESUME_TAILOR_MODEL","global.anthropic.claude-haiku-4-5-20251001-v1:0"
    ),
    "coverletter_generator":os.environ.get(
        "COVERLETTER_MODEL","global.anthropic.claude-haiku-4-5-20251001-v1:0"
    ),
    "interview_prep":os.environ.get(
        "INTERVIEW_MODEL","us.amazon.nova-2-lite-v1:0"
    )
}

# bedrock configs
BEDROCK_REGION=os.environ.get("AWS_REGION","us-east-1")
MAX_TOKENS=4000
TEMPERATURE=0.3

# DynamoDB config
DYNAMODB_TABLE=os.environ.get("APPLICATIONS_TABLE","job-applications")

# S3 config
RESUMES_BUCKET=os.environ.get("RESUMES_BUCKET","job-assistant-resumes")

# Logging
LOG_LEVEL=os.environ.get("LOG_LEVEL","INFO")

# cost tracking -pricing is shown in AWS Bedrock pricing website-
COST_PER_1K_TOKENS={
    "us.amazon.nova-2-lite-v1:0":{
        "input":0.0003, # 0.3 per million
        "output":0.0025 # 2.5 per million
    },
    "global.anthropic.claude-haiku-4-5-20251001-v1:0":{
        "input":0.001, # 1 per 1M
        "output":0.005 # 5 per 1M
    },
    "meta.llama3-1-70b-instruct-v1:0": {
        "input": 0.00099,   # $0.99 per 1M tokens
        "output": 0.00099   # $0.99 per 1M tokens
    }
}