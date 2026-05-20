import requests
import json
import time
import os
from dotenv import load_dotenv
load_dotenv()
from typing import Any
import prompts
from utils import logger


TIMEOUT = 10.0
DOUBAO_API_KEY = os.environ["DOUBAO_API_KEY"]
DOUBAO_BASE_URL = os.environ["DOUBAO_BASE_URL"]
DOUBAO_MODEL_NAME = os.environ["DOUBAO_MODEL_NAME"]
NLG_PROMPT = prompts.NLG_PROMPT


def request_nlg(query, tool_response):
    try:
        headers = {
            "Content-Type": "application/json",
            "Authorization": DOUBAO_API_KEY
        }
        messages = [
            {"role": "user", "content": NLG_PROMPT.format(query, tool_response)}
        ]

        body = dict(
            model=DOUBAO_MODEL_NAME,
            messages=messages,
        )
        response = requests.post(
            DOUBAO_BASE_URL,
            headers=headers,
            json=body,
            timeout=TIMEOUT
        )
        if response.status_code != 200:
            logger.error(f"NLG API error: status={response.status_code}")
            return ""
        response = response.json()
        if "choices" not in response:
            logger.error(f"NLG API no choices: {json.dumps(response, ensure_ascii=False)[:200]}")
            return ""
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

