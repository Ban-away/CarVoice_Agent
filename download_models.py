#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
下载项目所需公开模型到本地 train/pretrained 目录。

默认行为：
1. 读取 CARVOICE_BASE_DIR / PROJECT_HOME / 当前工作目录
2. 下载项目训练所需的两个基础模型
3. 按 train/models/*.py 中定义的本地路径落盘

示例：
  python download_models.py
  python download_models.py --base-dir D:\\Development\\Exercise\\0_personal_project\\CarVoice_Agent
  python download_models.py --hf-token <token>
"""

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

import argparse
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List

from huggingface_hub import snapshot_download


@dataclass(frozen=True)
class ModelSpec:
    name: str
    repo_id: str
    target_rel_path: str
    required: bool = True


MODEL_PRESETS: Dict[str, List[ModelSpec]] = {
    "core": [
        ModelSpec("chinese_roberta_wwm_ext", "hfl/chinese-roberta-wwm-ext", "train/pretrained/chinese_roberta_wwm_ext"),
        ModelSpec("roberta_tiny_clue", "clue/roberta_chinese_3L312_clue_tiny", "train/pretrained/roberta_tiny_clue"),
    ]
}


def resolve_base_dir(user_base_dir: str = "") -> Path:
    if user_base_dir:
        return Path(user_base_dir).resolve()
    env_base = os.getenv("CARVOICE_BASE_DIR") or os.getenv("PROJECT_HOME")
    if env_base:
        return Path(env_base).resolve()
    return Path.cwd().resolve()


def download_one(spec: ModelSpec, base_dir: Path, hf_token: str = "") -> None:
    target_dir = base_dir / Path(spec.target_rel_path)
    target_dir.mkdir(parents=True, exist_ok=True)
    print(f"[INFO] downloading {spec.name} -> {target_dir}")
    snapshot_download(
        repo_id=spec.repo_id,
        local_dir=str(target_dir),
        local_dir_use_symlinks=False,
        token=hf_token or None,
    )
    print(f"[DONE] {spec.name}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Download required models for CarVoice_Agent.")
    parser.add_argument(
        "--preset",
        choices=MODEL_PRESETS.keys(),
        default="core",
        help="Model preset to download. Default: core.",
    )
    parser.add_argument(
        "--base-dir",
        default="",
        help="Project base directory. Defaults to CARVOICE_BASE_DIR / PROJECT_HOME / current directory.",
    )
    parser.add_argument(
        "--hf-token",
        default=os.getenv("HF_TOKEN", ""),
        help="HuggingFace token for gated/private models.",
    )
    args = parser.parse_args()

    base_dir = resolve_base_dir(args.base_dir)
    print(f"[INFO] base_dir = {base_dir}")
    print(f"[INFO] preset = {args.preset}")

    failed: List[str] = []
    for spec in MODEL_PRESETS[args.preset]:
        try:
            download_one(spec, base_dir, args.hf_token)
        except Exception as exc:  # noqa: BLE001
            level = "ERROR" if spec.required else "WARN"
            print(f"[{level}] {spec.name} download failed: {exc}")
            if spec.required:
                failed.append(spec.name)

    print("\n[NOTE] 以下产物不在公开下载脚本范围内，需要本地训练或手动准备：")
    print("       1) train/saved/intent/bert.ckpt")
    print("       2) train/saved/reject/bert_tiny.ckpt")

    if failed:
        raise SystemExit(f"[FAILED] required models not downloaded: {', '.join(failed)}")
    print("[SUCCESS] model download finished.")


if __name__ == "__main__":
    main()