# 🚗 CarVoice_Agent

> 面向车载语音交互场景的**任务型对话 Agent 系统**  
> 覆盖入口编排、意图识别、拒识过滤、函数调用式 NLU、对话管理、闲聊兜底、多轮改写与端到端评测流程

[![Python](https://img.shields.io/badge/Python-3.9%2B-3776ab?logo=python&logoColor=white)](https://www.python.org)
[![PyTorch](https://img.shields.io/badge/PyTorch-2.0%2B-ee4c2c?logo=pytorch&logoColor=white)](https://pytorch.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115%2B-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Flask-SocketIO](https://img.shields.io/badge/Flask--SocketIO-5.x-black?logo=flask&logoColor=white)](https://flask-socketio.readthedocs.io)
[![Redis](https://img.shields.io/badge/Redis-Required-dc382d?logo=redis&logoColor=white)](https://redis.io)

---

## 📑 目录

- [🔧 技术与模块](#技术与模块)
- [📦 项目结构](#项目结构)
- [🔄 端到端链路](#端到端链路)
- [🧠 数据与模型目录说明](#数据与模型目录说明)
- [⚙️ 配置要点](#配置要点)
- [📊 训练与评测](#训练与评测)
- [⚡ 快速运行](#快速运行)
- [⚠️ 已知限制](#已知限制)

---

## 🔧 技术与模块

### 📋 技术栈概览

<table>
<tr>
<td width="25%"><b>🚪 入口服务</b></td>
<td width="75%">
Flask + Flask-SocketIO，多路并发编排（ThreadPoolExecutor）
</td>
</tr>
<tr>
<td><b>🧠 NLU</b></td>
<td>
FastAPI 微服务 + LLM Function Calling + 槽位映射后处理
</td>
</tr>
<tr>
<td><b>🎯 分类模型</b></td>
<td>
PyTorch BERT / BERT-Tiny：意图识别（Top-K）+ 拒识二分类
</td>
</tr>
<tr>
<td><b>💬 闲聊兜底</b></td>
<td>
豆包流式对话接口，支持多轮历史拼接与分帧输出
</td>
</tr>
<tr>
<td><b>🗄️ 状态管理</b></td>
<td>
Redis 会话缓存（仲裁历史、改写历史、闲聊历史、上一轮状态）
</td>
</tr>
<tr>
<td><b>🧩 扩展能力</b></td>
<td>
MCP 工具服务（高德地图、音乐检索等）
</td>
</tr>
</table>

### 🧱 核心模块职责

| 模块 | 主要文件 | 作用 |
|:---:|:---|:---|
| 入口编排 | `start.py` | 接收 `request_nlu`，并发调度仲裁/拒识/NLU/相关性/闲聊 |
| Socket 客户端测试 | `dialog.py` / `test.py` | 与入口服务建立 Socket 通信，收发分帧结果 |
| 语义客户端 | `client/` | `arbitration`、`rewrite`、`correlation`、`reject`、`nlu`、`stream_chat` |
| NLU 主服务 | `function_call/chatnlu_infer.py` | TopK 意图召回 + Function Calling + 槽位标准化 |
| 对话管理 | `function_call/dm/` | weather/maps/music 领域后处理 |
| 分类训练/推理 | `train/` | intent/reject 训练脚本、在线推理服务 |
| 配置与映射 | `config/` | 意图映射、槽位映射、环境配置 |
| 评测脚本 | `test/` + `e2e_score.py` | 多轮端到端压测与人工标注统计 |

---

## 📦 项目结构

```text
CarVoice_Agent/
├─ README.md
├─ requirements.txt
├─ server.sh                     # 一键启动脚本（微服务 + 入口）
├─ start.py                      # 入口服务（Flask-SocketIO）
├─ dialog.py                     # Socket 调用样例
├─ test.py                       # 多轮批量测试驱动
├─ e2e_score.py                  # 端到端准确率统计
└─ prompts.py                    # 提示词模板定义

├─ client/                       # 语义客户端（外部接口调用）
│  ├─ arbitration.py             # 领域仲裁（A/B/C/D -> task/chat）
│  ├─ rewrite.py                 # Query 改写
│  ├─ correlation.py             # 当前 query 与上轮相关性
│  ├─ reject.py                  # 拒识服务调用
│  ├─ nlu.py                     # NLU 服务调用
│  ├─ nlg.py                     # 自然语言生成
│  └─ stream_chat.py             # 闲聊流式处理
│
├─ function_call/                # Function Calling NLU
│  ├─ function.py                # 工具定义（意图函数签名）
│  ├─ slot_process.py            # 槽位值规整与映射
│  ├─ chatnlu_infer.py           # NLU FastAPI 服务（8009）
│  └─ dm/
│     ├─ factory.py              # DM 工厂
│     ├─ weather.py
│     ├─ maps.py
│     └─ music.py
│
├─ train/                        # 分类模型训练与服务
│  ├─ run.py                     # 训练入口
│  ├─ train_eval.py              # 训练/验证/测试
│  ├─ intent_infer.py            # 意图服务（8008）
│  ├─ reject_infer.py            # 拒识服务（8007）
│  ├─ data_helper.py             # 数据处理工具
│  ├─ data/
│  │  ├─ intent/                 # 意图数据（train/dev/test/class）
│  │  └─ reject/                 # 拒识数据（train/dev/test/class）
│  ├─ models/
│  │  ├─ bert.py                  # 意图识别模型（bert-large，平衡精度与效率）
│  │  └─ bert_tiny.py             # 拒识模型（3层BERT，极致效率，小模型大数据）
│  ├─ pretrained/                # 预训练模型目录
│  │  ├─ chinese_roberta_wwm_ext/
│  │  └─ roberta_tiny_clue/
│  ├─ saved/                     # 微调后模型保存目录
│  │  ├─ intent/
│  │  └─ reject/
│  ├─ result/                    # 训练日志
│  └─ core/                      # BERT 相关基础实现
│     ├─ __init__.py
│     ├─ file_utils.py            # 文件操作工具
│     ├─ modeling.py              # BERT 模型实现
│     ├─ optimization.py          # 优化器配置
│     └─ tokenization.py          # 分词工具
│
├─ config/
│  ├─ config.ini                 # 环境变量模板（shell export 风格）
│  ├─ class.txt                  # 意图ID-中文名-函数名映射
│  ├─ slot_intent.json           # 槽位字段映射
│  └─ new_map.json
│
├─ test/
│  ├─ data/                      # 单轮/多轮测试语料
│  ├─ result/                    # 预测结果与标注结果
│  ├─ intent_client.py           # 意图服务测试客户端
│  ├─ intent_benchmark.py        # 意图模型评测脚本
│  ├─ reject_client.py           # 拒识服务测试客户端
│  ├─ reject_benchmark.py        # 拒识模型评测脚本
│  ├─ nlu_client.py              # NLU服务测试客户端
│  └─ nlu_benchmark.py           # NLU模型评测脚本
│
├─ mcp_core/                     # MCP 扩展工具（高德、音乐）
│  ├─ amp_server.py              # 高德地图服务
│  ├─ music_server.py            # 音乐检索服务
│  └─ mcp_client.py              # MCP 客户端调用
├─ utils/                        # 日志、Redis 工具
│  ├─ logger.py                  # 日志工具
│  └─ redis_tool.py              # Redis 工具
└─ log/                          # 运行日志目录
```

---

## 🔄 端到端链路

### 🗺️ 在线推理主流程

```text
用户语音/文本
   ↓
start.py (SocketIO 入口)
   ↓ 并发调用
   ├─ arbitration.py  -> 任务/闲聊仲裁
   ├─ rewrite.py      -> 基于历史改写 query
   ├─ reject.py       -> 拒识二分类
   ├─ correlation.py  -> 相关性校验
   ├─ nlu.py          -> chatnlu-server (intent+slot)
   └─ stream_chat.py  -> 闲聊流式回复
   ↓
结果合并与分支策略
   ├─ 命中任务：输出 intent/function/slots (+ 可选 DM 工具结果)
   ├─ 命中闲聊：流式分帧输出
   └─ 命中拒识：统一拒识响应
```

### 🔧 微服务端口

| 服务 | 文件 | 默认端口 | 路径 |
|:---:|:---|:---:|:---|
| 入口服务 | `start.py` | 8080 | Socket 事件：`request_nlu` |
| 拒识服务 | `train/reject_infer.py` | 8007 | `POST /reject-server/v1` |
| 意图服务 | `train/intent_infer.py` | 8008 | `POST /intent-server/v1` |
| NLU 服务 | `function_call/chatnlu_infer.py` | 8009 | `POST /chatnlu-server/v1` |

---

## 🧠 数据与模型目录说明

### 📂 数据集位置

| 目录 | 说明 |
|:---:|:---|
| `train/data/intent/` | 意图分类训练、验证、测试数据 |
| `train/data/reject/` | 拒识分类训练、验证、测试数据 |
| `test/data/` | 单轮/多轮端到端评测样本 |
| `test/result/` | 推理输出与人工标注结果 |
| `config/class.txt` | 意图 ID 与函数映射（线上推理关键字典） |
| `config/slot_intent.json` | 槽位字段标准化映射 |

> **说明**：训练数据来源于线上，由专门的工程团队负责数据采集、清洗与标注。

### 📦 `pretrained` 与 `saved` 的作用

> 这两个目录是训练链路中的关键目录，项目默认会使用并依赖它们。

| 目录 | 作用 | 典型内容 |
|:---:|:---|:---|
| `train/pretrained/` | 存放基础预训练模型（作为初始化权重） | `chinese_roberta_wwm_ext/`、`roberta_tiny_clue/` |
| `train/saved/` | 存放微调后的任务模型（线上推理加载） | `intent/bert.ckpt`、`reject/bert_tiny.ckpt` |

模型路径在 `train/models/bert.py` 与 `train/models/bert_tiny.py` 中定义：

- `bert_path = ./pretrained/chinese_roberta_wwm_ext`（在 `train/` 目录下运行时生效）
- `save_path = ./saved/{dataset}/{model}.ckpt`（在 `train/` 目录下运行时生效）

---

## ⚙️ 配置要点

### 1) 环境变量

项目通过环境变量读取外部接口与服务地址。`config/config.ini` 提供了模板（内容实际是 shell `export` 风格）：

```bash
# 生成与仲裁模型
export API_KEY="Bearer xxxx"
export BASE_URL="https://ark.cn-beijing.volces.com/api/v3/chat/completions"
export BOT_URL="https://ark.cn-beijing.volces.com/api/v3/bots/chat/completions"

# 地图服务
export AMAP_MAPS_API_KEY="xxxx"

# 微服务地址
export REJECT_URL="http://127.0.0.1:8007/reject-server/v1"
export INTENT_URL="http://127.0.0.1:8008/intent-server/v1"
export NLU_URL="http://127.0.0.1:8009/chatnlu-server/v1"
export ENTRY_URL="http://127.0.0.1:8080/request_nlu"
```

### 2) Redis（自动启动）

使用 `bash server.sh` 一键启动时，**Redis 会自动启动**：
- 首次运行：自动下载并编译 Redis 6.0.8
- 后续运行：直接启动（不会重复下载）

Redis 用于会话历史和状态缓存：

- 仲裁历史：`voice:arbitration_history:*`
- 改写历史：`voice:rewrite_history:*`
- 闲聊历史：`voice:chat_history:*`
- 最近服务状态：`voice:last_service:*`

### 3) 目录准备

建议预先创建目录：

- `log/`
- `train/saved/intent/`
- `train/saved/reject/`
- `train/pretrained/chinese_roberta_wwm_ext/`
- `train/pretrained/roberta_tiny_clue/`

---

## 📊 训练与评测

### 1) 训练前准备

训练前需先加载环境变量：

```bash
source config/config.ini
```

### 2) 训练分类模型

```bash
cd train
# 训练意图模型（bert-large，平衡精度与效率）
python run.py --model bert --data intent

# 训练拒识模型（bert-tiny，极致效率，小模型大数据）
python run.py --model bert_tiny --data reject
```

训练完成后会输出到：

- `train/saved/intent/bert.ckpt`
- `train/saved/reject/bert_tiny.ckpt`

### 3) 服务化推理

- `train/intent_infer.py` 支持 TopK 意图召回
- `train/reject_infer.py` 支持阈值拒识判定

### 4) 端到端评测

```bash
# 生成端到端输出
python test.py

# 统计人工标注准确率
python e2e_score.py
```

`e2e_score.py` 会读取 `test/result/multi_test_output_labeled.txt`，按首列标注统计端到端准确率。

### 5) 性能测试（Locust）

使用 Locust 进行服务性能压测：

```bash
# 安装 Locust
pip install locust

# NLU 服务压测（端口 8009）
cd test
locust -f nlu_benchmark.py --host http://127.0.0.1:8009 --headless -u 10 -r 5 -t 60s

# 意图服务压测（端口 8008）
locust -f intent_benchmark.py --host http://127.0.0.1:8008 --headless -u 10 -r 5 -t 60s

# 拒识服务压测（端口 8007）
locust -f reject_benchmark.py --host http://127.0.0.1:8007 --headless -u 10 -r 5 -t 60s
```

**参数说明**：
| 参数 | 含义 |
|:---|:---|
| `-u 10` | 并发用户数 |
| `-r 5` | 每秒新增用户数 |
| `-t 60s` | 测试时长 |
| `--headless` | 无界面模式 |

---

## ⚡ 快速运行

### 0) 先下载基础模型

```bash
# 在项目根目录执行
python download_models.py

# 如需指定项目根目录或 HuggingFace Token
python download_models.py --base-dir . --hf-token <token>
```

> 该脚本会把两个基础模型下载到 `train/pretrained/`：
> `chinese_roberta_wwm_ext` 和 `roberta_tiny_clue`。

### 1) 安装依赖

```bash
pip install -r requirements.txt
```

### 2) 加载环境变量（Linux/macOS）

```bash
source config/config.ini
```

### 3) 启动服务

```bash
bash server.sh
```

### 方式一：脚本一键启动（推荐）

完成上面的 0-3 步后，直接执行 `bash server.sh` 即可，它会依次启动拒识、意图、NLU 和入口服务。

### 方式二：手动逐服务启动

```bash
# 终端 A：拒识
cd train
python reject_infer.py

# 终端 B：意图
cd train
python intent_infer.py

# 终端 C：NLU
cd function_call
python chatnlu_infer.py

# 终端 D：入口
cd .
python start.py
```

### Windows 启动提示

`config/config.ini` 使用的是 `export` 语法，不可直接在 `cmd` 中执行。可选方案：

1. 使用 Git Bash / WSL 执行 `source config/config.ini`
2. 在系统环境变量中手动配置上述键值
3. 改写为 `.bat` 版本后通过 `cmd` 启动

### 运行联调样例

```bash
# 单次 Socket 调用
python dialog.py

# 多轮批量测试（读取 test/data/multi_test.txt）
python test.py
```

---

## ⚠️ 已知限制

| 限制 | 说明 | 建议 |
|:---:|:---|:---|
| 配置文件命名 | `config.ini` 内容是 shell 脚本而非标准 INI | 可重命名为 `.env` 或 `env.sh` |
| 平台差异 | 一键脚本偏 Linux | Windows 推荐 Git Bash/WSL |
| 外部依赖 | 豆包 API、Redis、高德 API 需可用 | 启动前先健康检查 |
| 模型目录 | `train/pretrained/` 与 `train/saved/` 需提前准备 | 首次训练前先建目录并放入基座模型 |
| E2E 评估 | 最终准确率依赖人工标注 | 建议建立统一标注规范 |

---

## 📘 术语说明：意图与槽位

- **意图（Intent）**：用户要做什么，例如“导航到机场”“播放周杰伦”。
- **槽位（Slot）**：完成意图所需参数，例如 `地点=首都机场`、`歌手=周杰伦`。

本项目在 `function_call/slot_process.py` 中将模型返回参数做字段映射与归一化，最终输出结构化结果供业务执行。

---

<p align="center">
  <b>🚘 CarVoice Agent: Task First, Chat as Fallback</b><br/>
  <em>面向车载场景的可落地任务型对话系统</em>
</p>