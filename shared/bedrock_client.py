"""
Bedrock Client - Abstraction layer for AWS Bedrock API
Handles different model formats and provides unified interface
Updated for Nova 2, Claude Haiku 4.5, and Llama API schemas
"""

import json
import boto3
import logging
from typing import Dict, Any, Optional

logger=logging.getLogger()

class BedrockClient:
    """
    Unified client for AWS Bedrock models
    Abstraction for model-specific req/res formats
    """
    def __init__(self,model_id:str,region:str="us-east-1"):

        self.model_id=model_id
        self.region=region
        self.client=boto3.client(
            service_name='bedrock-runtime',
            region_name=region
        )

        # Model family for request formatting
        self.model_family= self._get_model_family(model_id)
        logger.info(f"Initialized Bedrock client with model: { model_id}")


    def _get_model_family(self,model_id:str) -> str:
        """
        Determine model family from model ID
        """
        if "anthropic.claude" in model_id:
            return "claude"
        elif "amazon.nova" in model_id or "amazon.titan" in model_id:
            return "amazon"
        elif "meta.llama" in model_id:
            return "llama"
        else:
            raise ValueError(f"Unsupported model family: {model_id}")
    
    def invoke(
            self,
            prompt:str,
            max_tokens:int =4000,
            temperature :float =0.3,
            system_prompt: Optional[str]=None
    )-> Dict[str,Any]:
        """
        Invoke Bedrock model with unified interface
        Args:
        prompt: User prompt
        max_tokens: maximum tokens to be used
        temperature: from 0 to 1 
        system_prompt: optional for Claude models
        """
        try:
            # Build request body based on model family
            request_body=self._build_request_body(
                prompt,max_tokens,temperature,system_prompt
            )
            logger.info(f"Invoking {self.model_id} with {len(prompt)} char prompt")

            # Call Bedrock API
            response=self.client.invoke_model(
                modelId=self.model_id,
                body=json.dumps(request_body)
            )
            # Parse response based on model family
            result=self._parse_response(response)
            
            logger.info(f"Received response: {result['usage']['output_tokens']} tokens")

            return result
        
        except Exception as e:
            logger.error(f"Bedrock invocation failed: {str(e)}")
            raise
        
    def _build_request_body(
            self,
            prompt:str,
            max_tokens:int,
            temperature:float,
            system_prompt: Optional[str]
    )-> Dict[str,Any]:
        """Build model specific request body"""

        if self.model_family=="claude":
            # Claude format API - Updated for Haiku 4.5
            body = {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": max_tokens,
                "temperature": temperature,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": prompt
                            }
                        ]
                    }
                ]
            }
            if system_prompt:
                body["system"]= system_prompt
            return body
        
        elif self.model_family=="amazon":
            # Amazon Nova 2 format - Updated
            body = {
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "text": prompt
                            }
                        ]
                    }
                ],
                "inferenceConfig": {
                    "maxTokens": max_tokens,
                    "temperature": temperature,
                    "topP": 0.9
                }
            }
            
            # Add system prompt if provided
            if system_prompt:
                body["system"] = [
                    {
                        "text": system_prompt
                    }
                ]
            
            return body
        
        elif self.model_family=="llama":
            return {
                "prompt": prompt,
                "max_gen_len":max_tokens,
                "temperature":temperature,
                "topP":0.9
            }
        else:
            raise ValueError(f"Unsupported model family: {self.model_family}")
    
    def _parse_response(self,response:Dict[str,Any])-> Dict[str,Any]:
        """ For parse model-specific response format"""
        # Read the response
        response_body=json.loads(response['body'].read())

        if self.model_family=="claude":
            # Claude response format - Updated for new schema as of Mar 2026
            content_text = ""
            for content_block in response_body['content']:
                if content_block.get('type') == 'text':
                    content_text = content_block['text']
                    break
            
            return {
                "content": content_text,
                "usage": {
                    "input_tokens": response_body['usage']['input_tokens'],
                    "output_tokens": response_body['usage']['output_tokens']
                },
                "stop_reason": response_body.get('stop_reason')
            }
        
        elif self.model_family=="amazon":
            # Amazon Nova response format - new schema as of Mar 2026
            content_text = ""
            
            # Extract text from content array
            if 'output' in response_body and 'message' in response_body['output']:
                for content_block in response_body['output']['message']['content']:
                    if 'text' in content_block:
                        content_text = content_block['text']
                        break
            
            return {
                "content": content_text,
                "usage": {
                    "input_tokens": response_body['usage']['inputTokens'],
                    "output_tokens": response_body['usage']['outputTokens']
                },
                "stop_reason": response_body.get('stopReason')
            }
        
        elif self.model_family=="llama":
            # Llama response format
            return{
                "content":response_body['generation'],
                "usage":{
                    "input_tokens":response_body.get('prompt_token_count',0),
                    "output_tokens":response_body.get('generation_token_count',0)
                }
            }
        else:
            raise ValueError(f"Unsupported model family : {self.model_family}")
        
    def calculate_cost(self,input_tokens:int,output_tokens:int)-> float:
        """ 
        calculate estimated cost for API call
        returns a cost in USD
        prices are taken from AWS docs in date of 14th Feb 2026 :)
        """
        cost_per_1k={
            "amazon.nova-2-lite-v1:0":{"input":0.0003,"output":0.0025},
            "anthropic.claude-haiku-4-5-20251001-v1:0":{"input":0.001,"output":0.005},
            # Llama models - Added
            "meta.llama3-1-70b-instruct-v1:0": {"input": 0.00099, "output": 0.00099},
            "meta.llama3-1-8b-instruct-v1:0": {"input": 0.0003, "output": 0.0006}
        }
        
        if self.model_id not in cost_per_1k:
            logger.warning(f"Cost data not available for {self.model_id}")
            return 0.0
        
        rates=cost_per_1k[self.model_id]
        input_cost=(input_tokens /1000 ) * rates["input"]
        output_cost=(output_tokens/1000) *rates["output"]

        return input_cost+output_cost
    
def create_client(model_id:str,region:str="us-east-1") -> BedrockClient:
    # Create Bedrock client with configs
    return BedrockClient(model_id,region)


    




