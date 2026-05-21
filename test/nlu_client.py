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
    "位置", "音源", "Extreme", "选项", "评分",
    "新闻类型", "歌曲心情", "歌曲主题", "歌曲场景", "歌曲语言", "歌曲流派",
    "歌曲年代", "风格", "电台类型", "驾驶模式", "系统主题", "桌面样式",
    "一级菜单设置项", "二级菜单设置项", "号码标签", "场景", "媒体收藏源",
    "水平方向", "垂直方向", "节目类型", "音质", "语速",
}


def _to_float(s):
    """尝试将字符串转为浮点数，失败返回 None"""
    try:
        s = s.strip().rstrip('%')
        return float(s)
    except (ValueError, TypeError):
        pass
    # 尝试解析分数如 "5/6", "-5/6", "4/5"
    try:
        if '/' in s:
            parts = s.split('/')
            if len(parts) == 2:
                return float(parts[0]) / float(parts[1])
    except (ValueError, TypeError, ZeroDivisionError):
        pass
    return None


def value_match(key, expected, predicted):
    """判断单个槽位值是否语义等价"""
    if expected == predicted:
        return True
    if expected is None or predicted is None:
        return False

    e, p = str(expected).strip(), str(predicted).strip()

    # 复合位置归一化：副驾、左后 ↔ 副对角
    if key == "位置":
        e, p = _normalize_pos(e), _normalize_pos(p)
        if e == p:
            return True

    # 数值等价：35% ≈ 0.35, -5/6 ≈ -0.833, 5/6 ≈ 0.833
    e_f, p_f = _to_float(e), _to_float(p)
    if e_f is not None and p_f is not None and abs(e_f - p_f) < 0.01:
        return True

    # 枚举类：精确匹配（不区分大小写）
    if key in ENUM_SLOTS:
        return e.lower() == p.lower()

    # 自由文本类：大小写归一后做包含判断（短串被长串包含即等价）
    e_low, p_low = e.lower(), p.lower()
    if len(e_low) >= 2 and (e_low in p_low or p_low in e_low):
        return True

    return False


import re as _re


def _normalize_pos(val):
    """将复合位置描述归一化为标准值（副驾、左后 → 副对角 等）"""
    v = val
    v = v.replace('主驾驶', '主驾').replace('副驾驶', '副驾')
    v = v.replace('右下方', '右后').replace('右后方', '右后').replace('右后侧', '右后')
    v = v.replace('左下方', '左后').replace('左后方', '左后').replace('左后侧', '左后')
    v = _re.sub(r'[、与跟以及还有，,\s]+', '和', v)
    parts = set(p for p in v.split('和') if p)
    if '主驾' in parts and '右后' in parts:
        return '主对角'
    if '副驾' in parts and '左后' in parts:
        return '副对角'
    if ('主驾' in parts and '副驾' in parts) or '主副驾' in parts:
        return '主副驾'
    return val


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