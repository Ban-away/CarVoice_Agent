import os
import json
import re
import time
import requests
import prompts
from utils import logger
from utils.redis_tool import RedisClient


MAX_HIS = 6
TTL = 45
REMIND_TIMEOUT = 2.5
REDIS_KEY = "voice:chat_history:{}"
_redis_client = RedisClient() 


DOUBAO_API_KEY = os.environ.get("API_KEY")
CHAT_URL = os.environ.get("CHAT_URL")
CHAT_MODEL = os.environ.get("CHAT_MODEL")
SYSTEM_PROMPT = prompts.BOT_CHAT_SYSTEM_PROMPT


def request_chat(query, sender_id, multiturn=True):
    # 如果没有配置 API_KEY，直接返回错误
    if not DOUBAO_API_KEY:
        logger.info("DOUBAO_API_KEY not configured, returning mock response")
        return "N"
    
    if multiturn:
        history = _redis_client.get(REDIS_KEY.format(sender_id))
        if history:
            history = json.loads(history)
        else:
            history = []
    else:
        history = []
    headers = {
        "Authorization": DOUBAO_API_KEY, 
        "Content-Type": "application/json"
    }
    messages_header = [
        {"role": "system", "content": SYSTEM_PROMPT}
    ]
    messages_now = [
        {"role": "user", "content": query}
    ]
    messages = messages_header + history + messages_now
    logger.info(f'request message:{messages}')
    data = {
        "model": CHAT_MODEL, # doubao-pro 32k, deepseek-v3/v3.1
        "messages": messages,
        "stream": True
    }
    try:
        response = requests.post(
            CHAT_URL,
            headers=headers,
            data=json.dumps(data),
            stream=True,
            timeout=TIMEOUT
        )
        if response.status_code != 200:
            logger.error(f"Bot Chat HTTP error: {response.status_code}, body: {response.text[:500]}")
            return "N"
        return response
    except Exception as e:
        logger.error("Bot Chat error:" + str(e))
        return "N"


def process_chat(response, query, sender_id):
    if response is None:
        response = "抱歉，此为敏感信息，请您换个问题"
        yield response
        return
    if response == "N":
        response = "抱歉，网络有点问题，请您再试一下"
        yield response
        return
    else:
        counter = 1
        uttrance = ""
        answer = ""
        for r in response.iter_lines(chunk_size=1, decode_unicode=False, delimiter=b'\n'):
            r = r.decode("utf-8").strip()
            if not r:
                continue
            r = json.loads(r.removeprefix("data: "))
            if "choices" not in r:
                logger.error(f"Bot Chat unexpected response: {r}")
                break
            if r["choices"][0].get("finish_reason") == "stop":
                break
            text = r["choices"][0].get("delta", {}).get("content")
            if not text:
                continue
            uttrance += text
            answer += text
            if re.search('，|。|？|；', text):
                yield uttrance
                uttrance = ""
                counter = 1
            if counter % 5 == 0:
                yield uttrance
                uttrance = ""
            counter += 1

        if uttrance and uttrance != "  " and uttrance != " ":
            yield uttrance

        logger.info(f"bot_Chat Result: {answer}")
        history = _redis_client.get(REDIS_KEY.format(sender_id))
        if history:
            history = json.loads(history)
        else:
            history = []
        history.append({"role": "user", "content": query})
        history.append({"role": "assistant", "content": answer})
        history = history[-MAX_HIS:]
        history_str = json.dumps(history, ensure_ascii=False)
        _redis_client.set(REDIS_KEY.format(sender_id), history_str, ex=TTL)


if __name__ == '__main__':
    while 1:
        query = input("-->")
        res = request_chat(query, '1')
        for frame in process_chat(res, query, '1'):
            print(frame)