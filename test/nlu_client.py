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
    import sys
    verbose = "--verbose" in sys.argv

    fd = open("data/single_slots_new.txt")
    data = fd.readlines()
    intent_right = 0
    slots_right = 0
    total = 0
    fail = 0
    intent_wrong_slots_wrong = 0
    intent_right_slots_wrong = 0
    intent_wrong_slots_right = 0
    slot_error_detail = {}

    for idx in tqdm(range(len(data)), disable=verbose, ncols=80, mininterval=0.5):
        line = data[idx]
        text, label, slots = line.strip().split("\t")
        response = get_completion(text)
        if response is None:
            fail += 1
            total += 1
            if verbose:
                print(f"[FAIL] {text}")
            continue
        pred_slots = response["slots"]
        slots = json.loads(slots)
        intent_ok = response["intent_id"] == label
        slots_ok = slots == pred_slots

        if intent_ok:
            intent_right += 1
        if slots_ok:
            slots_right += 1

        if not intent_ok and not slots_ok:
            intent_wrong_slots_wrong += 1
        elif intent_ok and not slots_ok:
            intent_right_slots_wrong += 1
        elif not intent_ok and slots_ok:
            intent_wrong_slots_right += 1

        if intent_ok and not slots_ok:
            if verbose:
                print(f"[SLOT MISS] {text}")
                print(f"  expected: {slots}")
                print(f"  predicted: {pred_slots}")
            # 统计错误类型
            for k in set(list(slots.keys()) + list(pred_slots.keys())):
                e_val = slots.get(k)
                p_val = pred_slots.get(k)
                if e_val != p_val:
                    err_type = f"{k}: expected={e_val}, got={p_val}"
                    slot_error_detail[err_type] = slot_error_detail.get(err_type, 0) + 1

        total += 1

    print(f"\ntest intent acc: {intent_right/total:.4f}, slots acc: {slots_right/total:.4f}, fail: {fail}/{total}")
    print(f"  intent正确 & slots正确: {slots_right}")
    print(f"  intent正确 & slots错误: {intent_right_slots_wrong}")
    print(f"  intent错误 & slots错误: {intent_wrong_slots_wrong}")
    print(f"  intent错误 & slots正确: {intent_wrong_slots_right}")
    print(f"\nTop slot errors (intent correct but slots wrong):")
    for err, cnt in sorted(slot_error_detail.items(), key=lambda x: -x[1])[:20]:
        print(f"  {cnt:4d}x  {err}")