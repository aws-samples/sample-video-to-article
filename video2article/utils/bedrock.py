import copy
import json
import logging
from typing import Optional

import boto3
from botocore.config import Config

DEFAULT_REGION = 'us-west-2'

def sanitize_bedrock_request(data: dict[str, any]) -> dict[str, any]:
    """Remove image data from the request for logging purposes."""
    sanitized = copy.deepcopy(data)

    if 'messages' in sanitized:
        for message in sanitized['messages']:
            if 'content' in message and isinstance(message['content'], list):
                for item in message['content']:
                    if item.get('type') == 'image' and 'source' in item:
                        item['source']['data'] = '[IMAGE DATA]'

    return sanitized

def create_message(messages: list[dict[str, any]],
    system: str = "",
    temperature: float = 0,
    max_tokens: int = 1024,
    stop_sequences: Optional[list[str]] = None,
    model_id: str = "us.anthropic.claude-3-7-sonnet-20250219-v1:0"
)-> str:
    """Generate a message using AWS Bedrock."""
    session = boto3.Session()
    client = session.client(
        service_name="bedrock-runtime",
        region_name=DEFAULT_REGION,
        config=Config(
            connect_timeout=150,
            read_timeout=150,
            retries={'max_attempts': 10})
    )

    body = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": max_tokens,
        "temperature": temperature,
        "stop_sequences": stop_sequences if stop_sequences else [],
        "system": system,
        "messages": messages
    }

    logging.debug("Calling Bedrock API: %s", sanitize_bedrock_request(body))

    response = client.invoke_model(
        modelId=model_id, body=json.dumps(body)
    )

    response_body = json.loads(response.get("body").read())
    logging.debug("Response from Bedrock API: %s", response_body)
    completion = response_body["content"][0]["text"]
    return completion
