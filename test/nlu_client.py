import os
from dotenv import load_dotenv
load_dotenv()
import requests
import uuid
import json
from tqdm import tqdm


URL = os.environ["NLU_URL"]


def get_completion(query):
    headers = {'Content-Type': 'application/json'}
    data = {"query": query, "trace_id": str(uuid.uuid1()), "enable_dm": False}
    try:
        response = requests.post(url=URL, headers=headers, data=json.dumps(data), timeout=30)
        if response.status_code != 200:
            return None
        return response.json()
    except Exception:
        return None

if __name__ == '__main__':
    fd = open("data/single_slots_new.txt")
    data = fd.readlines()
    intent_right = 0
    slots_right = 0
    total = 0
    fail = 0
    for idx in tqdm(range(len(data))):
        line = data[idx]
        text, label, slots = line.strip().split("\t")
        response = get_completion(text)
        if response is None:
            fail += 1
            total += 1
            continue
        pred_slots = response["slots"]
        slots = json.loads(slots)
        if slots == pred_slots:
            slots_right += 1
        if response["intent_id"] == label:
            intent_right += 1
        total += 1
    print(f"test intent acc: {intent_right/total:.4f}, slots acc: {slots_right/total:.4f}, fail: {fail}/{total}")