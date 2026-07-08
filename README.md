# -Python-ReAct-Agent
## 一、项目概述

本项目是一个 **纯 Python** 实现的 ReAct Agent，**不依赖 LangChain**。Agent 通过「观察 → 思考 → 行动 → 循环」模式，自主决定调用搜索工具或计算器来回答用户问题。

### 1.1 核心能力

- ReAct 模式：Thought / Action / Observation 循环
- 两个工具：联网搜索 + 安全计算器
- 支持 OpenAI 兼容 API（多服务商预设）
- Demo 模式：无 API Key 也可体验完整流程
- 纯标准库 LLM 调用（urllib，无 openai SDK）

### 1.2 项目结构

```
agent2/
├── react_agent.py      # ReAct 主循环 + CLI 入口
├── tools.py            # 搜索 + 计算器工具
├── config.py           # .env 配置 + 多服务商预设
├── requirements.txt    # 无第三方依赖（标准库即可）
├── .env.example        # API Key 模板
└── README.md           # 本文档
```

---

## 二、ReAct 架构设计

### 2.1 整体架构图

```
┌─────────────────────────────────────────────────────────┐
│                     用户 (CLI)                         │
│                  react_agent.py                          │
└──────────────────────────┬──────────────────────────────┘
                           │ question
                           ▼
┌─────────────────────────────────────────────────────────┐
│                   ReAct 主循环  run_react()               │
│                                                         │
│   ┌──────────┐    ┌──────────┐    ┌──────────────┐     │
│   │  Think   │ →  │   Act    │ →  │  Observe     │     │
│   │ LLM 推理  │    │ 执行工具  │    │ 记录结果      │     │
│   └────┬─────┘    └────┬─────┘    └──────┬───────┘     │
│        │               │                  │             │
│        │    scratchpad 累积轨迹            │             │
│        └───────────────┴──────────────────┘             │
│                    循环直到 finish                        │
└──────────────────────────┬──────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│                     工具层  tools.py                      │
│        search (DuckDuckGo + Wiki + 本地KB)               │
│        calculate (AST 安全计算)                           │
│        finish (结束并返回答案)                             │
└─────────────────────────────────────────────────────────┘
```

### 2.2 ReAct 执行流程

Agent 每步必须输出严格格式：

```
Thought: <推理过程，分析当前情况>
Action:  <工具调用>
```

可用 Action：

| Action | 格式 | 用途 |
|--------|------|------|
| 搜索 | `search[关键词]` | 查事实、定义、背景知识 |
| 计算 | `calculate[表达式]` | 精确数学计算 |
| 结束 | `finish[最终答案]` | 信息足够，回答用户 |

**示例：「光速是多少米每秒，乘以60等于多少」**

```
步骤1  Thought: 需要查资料
       Action:  search[光速]
       Observation: 真空中光速约为 299792458 米/秒

步骤2  Thought: 查到光速，计算乘以60
       Action:  calculate[299792458*60]
       Observation: 17987547480

步骤3  Thought: 计算完成，给出答案
       Action:  finish[17987547480]
```

### 2.3 LLM 调用层

```
config.py  resolve_llm_config()
    → 读取 .env / 服务商预设
    → 返回 (api_key, base_url, model)

react_agent.py  call_llm()
    → urllib POST /chat/completions
    → 纯标准库，无 openai SDK
```

---

## 三、模块功能详解

### 3.1 tools.py — 工具层

#### search — 联网搜索

```
优先级: 本地知识库 → DuckDuckGo Instant Answer → 维基百科(中) → 维基百科(英)
超时: 5 秒
```

本地知识库内置：Python、光速、ReAct、Agent 等常见条目，网络不可用时自动回退。

#### calculate — 安全计算器

- AST 白名单解析，禁止 `eval()` 任意代码
- 支持：`+` `-` `*` `/` `**` `sqrt()` `sin()` `cos()` 等
- 示例：`sqrt(144)+2**10` → `1036`

#### TOOLS 注册表

```python
TOOLS = {"search": search, "calculate": calculate}
```

### 3.2 react_agent.py — ReAct 主循环

| 函数 | 职责 |
|------|------|
| `parse_react(text)` | 正则解析 Thought / Action |
| `run_tool(action)` | 解析并 dispatch 工具，finish 返回 done=True |
| `build_messages(question, scratchpad)` | 构造 LLM 消息（含历史轨迹） |
| `run_react(question, think_fn)` | **核心循环**（约 50 行） |
| `demo_think(messages)` | 无 API Key 时的规则驱动假 LLM |

**核心循环逻辑：**

```python
for step in range(1, MAX_STEPS + 1):
    raw = think_fn(build_messages(question, scratchpad))  # 思考
    thought, action = parse_react(raw)
    obs, done = run_tool(action)                          # 行动
    scratchpad += f"Thought...\nAction...\nObservation..."  # 观察
    if done: return obs
```

### 3.3 config.py — 配置管理

支持多 LLM 服务商预设：

| provider | base_url | 默认模型 |
|----------|----------|----------|
| openai | api.openai.com | gpt-4o-mini |
| deepseek | api.deepseek.com | deepseek-chat |
| moonshot | api.moonshot.cn | moonshot-v1-8k |
| dashscope | dashscope.aliyuncs.com | qwen-plus |

---

## 四、使用方法

```bash
cd c:\Users\张煜坤\Desktop\agent2

# Demo 模式（无需 API Key）
python react_agent.py --demo "计算 sqrt(144)+2**10 等于多少"
python react_agent.py --demo "Python 是什么编程语言"
python react_agent.py --demo "光速是多少米每秒，乘以60等于多少"

# LLM 模式
copy .env.example .env
# 编辑 .env 填入 OPENAI_API_KEY
python react_agent.py "你的问题"

# 指定服务商
python react_agent.py --provider deepseek "问题"
```

---

## 五、与其他 Agent 项目对比

| 维度 | agent2（纯 Python） | agent4（LangChain） |
|------|---------------------|---------------------|
| 框架 | 无，手写 ReAct 循环 | LangChain + LangGraph |
| LLM 调用 | urllib 标准库 | langchain-openai |
| 工具注册 | 手动 TOOLS 字典 | @tool 装饰器 |
| 工具选择 | 正则解析 Action | LLM 原生 Tool Calling |
| Demo 模式 | ✅ 内置 | ❌ 需 API Key |
| 代码量 | ~150 行 | ~120 行 |
| 学习价值 | 理解 ReAct 原理 | 快速生产部署 |

---

## 六、扩展方向

| 改进 | 说明 |
|------|------|
| 多轮记忆 | scratchpad 跨会话持久化 |
| 流式输出 | LLM 流式 API + 逐字打印 |
| LangSmith 追踪 | 接入可观测性 |
| 更多工具 | 文件读写、数据库查询等 |

---

## 七、关键代码索引

| 函数 | 文件 | 职责 |
|------|------|------|
| `run_react()` | react_agent.py | ReAct 主循环 |
| `call_llm()` | react_agent.py | LLM API 调用 |
| `demo_think()` | react_agent.py | Demo 模式假 LLM |
| `search()` | tools.py | 联网搜索 |
| `calculate()` | tools.py | 安全计算 |
| `resolve_llm_config()` | config.py | 配置解析 |
