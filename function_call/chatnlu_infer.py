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
import re
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
    # 风向检测（吹脸/吹脚/吹窗）
    has_blow = bool(re.search(r'朝着|对着|往.*吹|吹脸|吹脚|吹窗|吹.*风', query))
    if has_blow:
        face = bool(re.search(r'脸', query))
        foot = bool(re.search(r'脚', query))
        win = bool(re.search(r'窗', query)) and "车窗" not in query
        if face and foot:
            return "吹脸吹脚"
        if win and foot:
            return "吹窗吹脚"
        if face:
            return "吹脸"
        if foot:
            return "吹脚"
        if win:
            return "吹窗"

    # 复合座位检测：交由 LLM + NLU prompt 判断，不在此硬编码
    # （测试数据中 "主驾和右后" 同样句式在不同意图下期望值不同，硬编码反而引入误判）

    keywords = [
        # 复合位置变体（放在单条目之前）
        ("主驾后面", "左后"), ("主驾后方", "左后"), ("主驾后头", "左后"), ("主驾后边", "左后"),
        ("副驾后面", "右后"), ("副驾后方", "右后"), ("副驾后头", "右后"), ("副驾后边", "右后"),
        ("后排左侧", "左后"), ("后排左边", "左后"), ("后排右侧", "右后"), ("后排右边", "右后"),
        ("后面左侧", "左后"), ("后面右侧", "右后"), ("右边后面", "右后"),
        ("后左", "左后"), ("后右", "右后"),
        ("右下方", "右后"), ("左下方", "左后"),
        ("主副驾", "主副驾"), ("主副驾驶", "主副驾"),
        # 单条目
        ("左后", "左后"), ("右后", "右后"),
        ("司机", "主驾"), ("驾驶位", "主驾"), ("左前", "主驾"),
        ("主驾", "主驾"), ("主驾驶", "主驾"),
        ("副驾", "副驾"), ("副驾驶", "副驾"), ("右前", "副驾"),
        ("前排", "前排"), ("后排", "后排"),
        ("前座椅", "前排"), ("前边", "前排"), ("第一排", "前排"),
        ("左面", "左侧"), ("左方", "左侧"), ("左部", "左侧"), ("左侧", "左侧"), ("左边", "左侧"),
        ("右面", "右侧"), ("右方", "右侧"), ("右部", "右侧"), ("右侧", "右侧"), ("右边", "右侧"),
        # "所有" 相关
        ("汽车里", "所有"), ("车里面", "所有"), ("车中", "所有"), ("车内", "所有"), ("车里", "所有"),
        ("所有的", "所有"), ("每一个", "所有"), ("所有", "所有"), ("每个", "所有"),
        ("全部", "所有"), ("全车", "所有"), ("全都", "所有"),
        ("前面", "前排"), ("后面", "后排"),
    ]
    for kw, val in keywords:
        if kw in query:
            return val
    return None


def _is_vague_degree(query):
    # 如果 query 中有明确的数字（含中文数字组合如"十一点七"），说明不是模糊程度
    if re.search(r'\d+', query):
        return False
    if re.search(r'十[一二三四五六七八九零]', query):
        return False
    vague_patterns = [
        "小一点", "大一点", "少一点", "多一点",
        "调低点", "调高点", "降低点", "升高点", "降点", "升点",
        "稍微", "略微", "稍稍",
        "再低", "再高", "再大", "再小", "再亮", "再暗",
        "低些", "高些", "暗些", "亮些", "大些", "小些", "降些", "弱些",
        "暗点", "调暗点", "调一调",
        "别太用力", "别太大",
        "降一降", "加重点", "别那么大", "轻点",
    ]
    # "一点"需排除"有点"、"好一点"等非程度表达
    if "一点" in query and not re.search(r'(有|好|差|看)一点', query):
        return True
    # "一些"需排除"那些"、"这些"、"哪些"等
    if "一些" in query and not re.search(r'[那这哪]些', query):
        return True
    return any(p in query for p in vague_patterns)


def _cn_num(s):
    """中文数字转阿拉伯数字，仅处理含'十'的简单情况"""
    cn_map = {"零": "0", "一": "1", "二": "2", "三": "3", "四": "4",
              "五": "5", "六": "6", "七": "7", "八": "8", "九": "9"}
    if "十" not in s:
        return "".join(cn_map.get(ch, ch) for ch in s)
    parts = s.split("十")
    if len(parts) == 2:
        left = cn_map.get(parts[0], parts[0]) if parts[0] else "1"
        right = cn_map.get(parts[1], parts[1]) if parts[1] else "0"
        return left + right
    return "".join(cn_map.get(ch, ch) for ch in s)


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

    # 过滤 LLM 幻觉值
    for k in list(slots.keys()):
        if k == "位置" and slots[k] == "Unknown":
            del slots[k]
        elif k == "选项" and slots[k] == "1" and "第" not in query:
            del slots[k]

    # Check_Car_Condition 参数幻觉过滤
    if func_name == "Check_Car_Condition":
        car_kw = {
            "tire": ["胎压", "轮胎"],
            "gas": ["油耗", "油量", "耗油", "耗几升"],
            "range": ["续航", "剩余油", "还能跑", "能跑多", "该去加油", "去加油"],
            "total": ["总里程", "总公里", "总共.*公里", "跑了.*公里", "行驶里程"],
            "Maintenance": ["保养", "维保"],
        }
        for k in list(slots.keys()):
            if k in car_kw:
                if not any(re.search(kw, query) for kw in car_kw[k]):
                    del slots[k]

    # Go_POI: POI=目的地 幻觉过滤
    if func_name == "Go_POI" and "POI" in slots and slots["POI"] == "目的地":
        if not re.search(r'目的地|公司地址|公司所在地|我家|导航.*设为', query):
            del slots["POI"]

    # 媒体源=USB音乐 幻觉过滤
    if "媒体源" in slots and slots["媒体源"] == "USB音乐":
        if not re.search(r'usb|USB|U盘|u盘', query):
            del slots["媒体源"]

    # 音源=所有 幻觉过滤：仅当 query 完全没有音源相关关键词时才删除
    if "音源" in slots and slots["音源"] == "所有":
        sound_kw = ["全部", "所有", "统统", "静音", "安静", "听不见", "音量"]
        if not any(kw in query for kw in sound_kw):
            del slots["音源"]

    # 关键词兜底：补充 LLM 遗漏的槽位
    func_slot_def = slot_map.get(func_name)
    if isinstance(func_slot_def, dict):
        expected_keys = set(func_slot_def.values())
        if "位置" in expected_keys and "位置" not in slots:
            pos = _extract_position(query)
            # "车里"/"车内"/"车中" 只在 Set_/Dec_/Inc_ 类函数中映射为 "所有"
            if pos == "所有" and func_name:
                if not any(func_name.startswith(p) for p in
                           ["Set_", "Dec_", "Inc_", "Open_Air_Condition_Auto",
                            "Close_Air_Condition_Auto", "Open_Air_Condition_Sync",
                            "Close_Air_Condition_Sync"]):
                    explicit_all = any(kw in query for kw in
                                       ["所有", "全部", "每一个", "全车", "全都", "所有的", "每个"])
                    if not explicit_all:
                        pos = None
            if pos:
                slots["位置"] = pos
        if "Extreme" in expected_keys and "Extreme" not in slots:
            ext = _extract_extreme(query)
            if ext:
                slots["Extreme"] = ext
        # number 兜底：仅在无 Extreme 且函数非音量类时补充
        if "number" in expected_keys and "number" not in slots and "Extreme" not in slots:
            if func_name and "Sound_Volume" not in func_name:
                if _is_vague_degree(query):
                    slots["number"] = "1"

    # 格式修正：节目名称去除多余的"第"
    if "节目名称" in slots:
        val = slots["节目名称"]
        val = re.sub(r'第(\d+)', r'\1', val)
        val = re.sub(r'第([一二三四五六七八九十]+)', lambda m: _cn_num(m.group(1)), val)
        slots["节目名称"] = val

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