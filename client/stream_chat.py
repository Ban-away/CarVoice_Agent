import os
from dotenv import load_dotenv
load_dotenv()
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


DOUBAO_API_KEY = os.environ["DOUBAO_API_KEY"]
DOUBAO_BASE_URL = os.environ["DOUBAO_BASE_URL"]
DOUBAO_MODEL_NAME = os.environ["DOUBAO_MODEL_NAME"]
SYSTEM_PROMPT = prompts.BOT_CHAT_SYSTEM_PROMPT


def request_chat(query, sender_id, multiturn=True):
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
        "model": DOUBAO_MODEL_NAME,
        "messages": messages,
        "stream": True
    }
    try:
        response = requests.post(
            DOUBAO_BASE_URL,
            headers=headers,
            data=json.dumps(data),
            stream=True,
            timeout=REMIND_TIMEOUT
        )
        if response.status_code != 200:
            logger.error(f"Chat API error: status={response.status_code}")
            return "N"
        return response
    except Exception as e:
        logger.error("Bot Chat error:" + str(e))
        return "N"


def process_chat(response, query, sender_id):
    if response is None:
        yield "抱歉，此为敏感信息，请您换个问题"
        return
    if response == "N":
        yield "抱歉，网络有点问题，请您再试一下"
        return
    counter = 1
    uttrance = ""
    answer = ""
    for r in response.iter_lines(chunk_size=1, decode_unicode=False, delimiter=b'\n'):
        r = r.decode("utf-8").strip()
        if not r:
            continue
        r = r.removeprefix("data: ")
        if r == "[DONE]":
            break
        try:
            r = json.loads(r)
        except json.JSONDecodeError:
            continue
        if "choices" not in r:
            continue
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
        res = request_doubao_bot(query, '1', '2')
        for frame in process_chat_bot(res, query, '1', time.time()):
            print(frame)

