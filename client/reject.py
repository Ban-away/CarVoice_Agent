import json
import requests
import re
import os
from utils import logger
from typing import List


THRESHOLD = float(os.environ.get("REJECT_THRESHOLD", 0.3))
REJECT_URL = os.environ.get("REJECT_URL", "http://127.0.0.1:8007/reject-server/v1")


def request_reject(query, trace_id):
    headers = {
        "Content-Type":"application/json"
    }
    payload = json.dumps({
        "query": query,
        "thres": THRESHOLD,
        "trace_id": trace_id
    })
    try:
        response = requests.post(
            REJECT_URL,
            headers=headers,
            data=payload
        )
        res = response.json()
        text = res["data"]
        logger.info(f"拒识模型的输出：{text}")
    except Exception as e:
        logger.error(f"call reject failed:{e}")
        text = "是"
    return text


if __name__ == '__main__':
    while True:
        query = input("Input:")
        res = request_reject(query, "123")
        print(res)