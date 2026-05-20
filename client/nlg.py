import requests
import json
import time
import os
from typing import Any
import prompts
from utils import logger


TIMEOUT = 10.0
API_KEY = os.environ["DOUBAO_API_KEY"]
BASE_URL = os.environ["DOUBAO_BASE_URL"]
MODEL_NAME = os.environ["DOUBAO_MODEL_NAME"]
NLG_PROMPT = prompts.NLG_PROMPT


def request_nlg(query, tool_response):
    try:
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {API_KEY}"
        }
        messages = [
            {"role": "user", "content": NLG_PROMPT.format(query, tool_response)}
        ]

        body = dict(
            model=MODEL_NAME,
            messages=messages,
        )
        response = requests.post(
            BASE_URL,
            headers=headers,
            json=body,
            timeout=TIMEOUT
        )
        response = response.json()
        answer = response["choices"][0]["message"]["content"]
        logger.info(f"NLG结果: {answer}")
        return answer

    except Exception:
        logger.error("Call NLG API failed.")
        return ""


if __name__ == "__main__":
    
    query = "今天天气怎么样"
    tool_response = "城市：北京市\n天气：阴\n温度：21度\n风向：东北\n风力：1-3级"

    res = request_nlg(query, tool_response)
    print(res)