import os
from dotenv import load_dotenv
load_dotenv()
import requests
import uuid
import json
from tqdm import tqdm


URL = os.environ["NLU_URL"]


# 枚举类槽位：系统应该归一化到标准值，做精确匹配
ENUM_SLOTS = {
    "位置", "音源", "Extreme", "选项", "评分", "date", "city",
    "新闻类型", "歌曲心情", "歌曲主题", "歌曲场景", "歌曲语言", "歌曲流派",
    "歌曲年代", "风格", "电台类型", "驾驶模式", "系统主题", "桌面样式",
    "一级菜单设置项", "二级菜单设置项", "号码标签", "场景", "媒体收藏源",
    "水平方向", "垂直方向", "节目类型", "音质", "语速",
}


def value_match(key, expected, predicted):
    """判断单个槽位值是否语义等价"""
    if expected == predicted:
        return True
    if expected is None or predicted is None:
        return False

    e, p = str(expected).strip(), str(predicted).strip()

    # 枚举类：精确匹配（不区分大小写）
    if key in ENUM_SLOTS:
        return e.lower() == p.lower()

    # 自由文本类：大小写归一后做包含判断（短串被长串包含即等价）
    e_low, p_low = e.lower(), p.lower()
    if len(e_low) >= 2 and (e_low in p_low or p_low in e_low):
        return True

    return False


# key 等价组：不同 key 名但语义相同的槽位
_KEY_EQUIV = {
    "ratio": "number",
    "number": "number",
}


def _resolve_key(key):
    """将等价 key 映射到统一名称"""
    return _KEY_EQUIV.get(key, key)


def slots_match(expected, predicted):
    """判断 predicted 是否覆盖了所有 expected 槽位（允许预测多出槽位）"""
    pred_mapped = {_resolve_key(k): v for k, v in predicted.items()}
    for k, v in expected.items():
        rk = _resolve_key(k)
        if rk not in pred_mapped:
            # Extreme 已覆盖时 number 冗余，跳过
            if rk == "number" and "Extreme" in pred_mapped:
                continue
            return False
        if not value_match(k, v, pred_mapped[rk]):
            return False
    return True


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

    pbar = tqdm(range(len(data)), ncols=80, mininterval=0.5)
    for idx in pbar:
        line = data[idx]
        text, label, slots = line.strip().split("\t")
        response = get_completion(text)
        if response is None:
            fail += 1
            total += 1
            if verbose:
                pbar.write(f"[FAIL] {text}")
            continue
        pred_slots = response["slots"]
        slots = json.loads(slots)
        intent_ok = response["intent_id"] == label
        slots_ok = slots_match(slots, pred_slots)

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
                pbar.write(f"[SLOT MISS] {text}")
                pbar.write(f"  expected: {slots}")
                pbar.write(f"  predicted: {pred_slots}")
            # 统计错误类型
            for k in set(list(slots.keys()) + list(pred_slots.keys())):
                e_val = slots.get(k)
                p_val = pred_slots.get(k)
                if not value_match(k, e_val, p_val):
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