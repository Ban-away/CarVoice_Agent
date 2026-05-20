import os
from dotenv import load_dotenv
load_dotenv()
import json
import uuid
import random
import asyncio
import numpy as np
import requests
import base64
import time
import uvicorn
import prompts
from slot_process import intent_slot
from function import tools1
from fastapi import FastAPI, Request
from concurrent.futures import ThreadPoolExecutor
from utils import logger
from dm.factory import DMFactory


## 创建FastAPI应用
app = FastAPI()


MAX_CONF = 0.98
TIMEOUT = 5
INTENT_URL = os.environ["INTENT_URL"]
API_KEY = os.environ["DOUBAO_API_KEY"]
BASE_URL = os.environ["DOUBAO_BASE_URL"]


id2func = {}
func2name = {}
name2id = {}
with open("../config/class.txt", 'r', encoding='utf-8') as mapfile:
    for line in mapfile:
        id, name, func = line.strip().split(":")
        id2func[id] = func
        func2name[func] = name
        name2id[name] = id

tool_map = {}
with open("../config/slot_intent.json", "r", encoding="utf-8") as slotfile:
    slot_map = json.load(slotfile)
    for item in tools1:
        name = item["function"]["name"]
        if name not in tool_map.keys():
            lst = [item]
            new_dict = {name: lst}
            tool_map.update(new_dict)
        else:
            tool_map.get(name).append(item)


def send_messages(messages, tool_lst):
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "model": os.environ["DOUBAO_MODEL_NAME"],
        "messages": messages,
        "tools": tool_lst,
        "temperature": 1e-6,
        "top_p": 0
    }
    try:
        response = requests.post(
            BASE_URL,
            headers=headers,
            data=json.dumps(data),
            timeout=TIMEOUT
        )
        if response.status_code != 200:
            logger.error(f"NLU API error: status={response.status_code}, body={response.text[:200]}")
            return None
        res = response.json()
        if "choices" not in res:
            logger.error(f"NLU API no choices: {json.dumps(res, ensure_ascii=False)[:200]}")
            return None
        return res['choices'][0]['message']['tool_calls']
    except Exception as e:
        logger.error(f"Doubao error: {e}")
        return None


def intent_recall(query, trace_id):
    headers = {'Content-Type': 'application/json'}
    data = {"query": query, "trace_id": str(uuid.uuid1())}
    response = requests.post(url=INTENT_URL, headers=headers, data=json.dumps(data))
    return response.json()


def _extract_position(query):
    # 优先检测复合位置：主驾+右后→主对角，副驾+左后→副对角
    has_main = any(kw in query for kw in ["主驾", "主驾驶"])
    has_vice = any(kw in query for kw in ["副驾", "副驾驶"])
    has_right_rear = any(kw in query for kw in ["右后", "右下方", "右后方", "后排右", "右边后面"])
    has_left_rear = any(kw in query for kw in ["左后", "左下方", "左后方", "后排左"])
    if has_main and has_right_rear:
        return "主对角"
    if has_vice and has_left_rear:
        return "副对角"

    keywords = [
        ("主驾后面", "左后"), ("副驾后面", "右后"),
        ("主副驾", "主副驾"), ("主副驾驶", "主副驾"),
        ("左后", "左后"), ("右后", "右后"),
        ("主驾", "主驾"), ("副驾", "副驾"),
        ("前排", "前排"), ("后排", "后排"),
        ("左侧", "左侧"), ("右侧", "右侧"),
        ("所有的", "所有"), ("每一个", "所有"), ("所有", "所有"), ("每个", "所有"), ("全部", "所有"),
        ("左边", "左侧"), ("右边", "右侧"),
        ("前面", "前排"), ("后面", "后排"),
        ("主驾驶", "主驾"), ("副驾驶", "副驾"),
    ]
    for kw, val in keywords:
        if kw in query:
            return val
    return None


def _is_vague_degree(query):
    vague_patterns = [
        "一点", "一些", "些", "小一点", "大一点", "少一点", "多一点",
        "调低点", "调高点", "降低点", "升高点", "降点", "升点",
        "稍微", "略微", "稍稍", "轻微", "些微",
        "再低", "再高", "再大", "再小", "再亮", "再暗",
    ]
    return any(p in query for p in vague_patterns)


def _extract_extreme(query):
    max_kw = ["最大", "最高", "最强", "最亮", "最热", "最足"]
    min_kw = ["最小", "最低", "最弱", "最暗", "最冷"]
    for kw in max_kw:
        if kw in query:
            return "最大"
    for kw in min_kw:
        if kw in query:
            return "最小"
    return None


def predict(query, trace_id):
    try:
        start = time.time()
        intent_rec = intent_recall(query, trace_id)
        results = intent_rec["data"].split(",")
        max_score = max([float(k) for k in intent_rec["score"].split(",")])
        logger.info(f"top5：{intent_rec['data']}, scores: {intent_rec['score']}, cost: {time.time() - start}")

        now_tool = []
        for t in results:
            func = id2func.get(t)
            lst_a = tool_map.get(func)
            if lst_a:
                for s in lst_a:
                    now_tool.append(s)
            else:
                continue

        header = [{"role": "system", "content": prompts.NLU_SYSTEM_PROMPT}]
        context = [{"role": "user", "content": query}]
        messages = header + context
        start_time = time.time()
        result = send_messages(messages, now_tool)
        logger.info(f"llm结果：{result}")
        logger.info(f"function调用时间:{time.time() - start_time}")
        if not result:
            # LLM未返回tool_calls，使用BERT的top1预测
            top_func = id2func.get(results[0])
            top_name = func2name.get(top_func)
            if top_func and top_func != "Unknown":
                logger.info(f"LLM未匹配，回退BERT预测: {top_name}-{top_func}")
                return f"{top_name}-无"
            return "未知-无"

        nlu = intent_slot(result, func2name, slot_map)
    except:
        return "未知-无"

    logger.info(f"返回结果：{nlu}")

    return nlu


@app.post("/chatnlu-server/v1")
async def inference(request: Request):
    json_info = await request.json()

    begin = time.time()
    query = json_info.get("query")
    enable_dm = json_info.get("enable_dm", True)
    trace_id = json_info.get("trace_id", "1")

    # 抽取意图和槽位（同步predict放入线程池，避免阻塞事件循环）
    loop = asyncio.get_event_loop()
    nlu = await loop.run_in_executor(None, predict, query, trace_id)


    # NLU后处理
    nlu_items = nlu.split("-")
    intent = nlu_items[0]
    if len(nlu_items) > 2:
        slots_str = "-".join(nlu_items[1:])
    else:
        slots_str = nlu_items[1]

    if slots_str != "无":
        slots = {}
        for item in slots_str.split(","):
            if ":" in item:
                if len(item.split(":")) != 2:
                    continue
                k, v = item.split(":")
                slots[k] = v
    else:
        slots = {}
    intent_id = name2id.get(intent)
    func_name = id2func.get(intent_id)

    # 关键词兜底：补充 LLM 遗漏的槽位
    func_slot_def = slot_map.get(func_name)
    if isinstance(func_slot_def, dict):
        expected_keys = set(func_slot_def.values())
        if "位置" in expected_keys and "位置" not in slots:
            pos = _extract_position(query)
            if pos:
                slots["位置"] = pos
        if "number" in expected_keys and "number" not in slots:
            if _is_vague_degree(query):
                slots["number"] = "1"
        if "Extreme" in expected_keys and "Extreme" not in slots:
            ext = _extract_extreme(query)
            if ext:
                slots["Extreme"] = ext

    response = {
        "query": query,
        "trace_id": trace_id,
        "intent": intent,
        "intent_id": intent_id,
        "function": func_name,
        "slots": slots,
    }

    if enable_dm:
        for name in ["weather", "music", "maps"]:
            dm_result = await DMFactory.get(name)(func_name, query, slots)
            if dm_result:
                tool_response, nlg = dm_result
                response["tool"] = tool_response
                response["nlg"] = nlg

    cost = time.time() - begin
    response["cost"] = cost

    return response

if __name__ == '__main__':
    import os
    port = int(os.environ['NLU_PORT'])
    uvicorn.run("chatnlu_infer:app", host='0.0.0.0', port=port, workers=4)