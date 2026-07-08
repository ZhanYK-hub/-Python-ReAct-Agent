#!/usr/bin/env python3
"""
ReAct CLI Agent — 纯 Python，不依赖 LangChain

核心循环（约 50 行）：
    观察(Observe) → 思考(Thought) → 行动(Action) → 观察(Observation) → 循环

用法：
    python react_agent.py --demo "计算 sqrt(144)+2**10"
    set OPENAI_API_KEY=sk-... && python react_agent.py "光速是多少米每秒，乘以60等于多少"
"""
import argparse, json, os, re, sys, urllib.error, urllib.request
from tools import TOOLS
from config import load_dotenv
load_dotenv()

MAX_STEPS = 8

SYSTEM = """你是 ReAct 风格的 CLI Agent，可自主决定查资料还是算数。

每步严格输出：
Thought: <推理过程>
Action: <工具调用>

工具：
- search[关键词]       — 查事实、定义、背景知识
- calculate[数学表达式] — 精确计算（支持 + - * / ** sqrt 等）
- finish[最终答案]     — 信息足够时回答用户

先思考再行动。可先 search 再 calculate，或反之。
"""

RE_T = re.compile(r"Thought:\s*(.+?)(?=\nAction:|\Z)", re.S | re.I)
RE_A = re.compile(r"Action:\s*(.+)", re.S | re.I)
RE_TOOL = re.compile(r"^(search|calculate|finish)\[(.*)\]\s*$", re.S | re.I)

def call_llm(messages, api_key, base_url, model):
    payload = json.dumps({"model": model, "messages": messages, "temperature": 0.2}, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(base_url.rstrip("/") + "/chat/completions", data=payload,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}, method="POST")
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode())["choices"][0]["message"]["content"]

def parse_react(text):
    t, a = RE_T.search(text), RE_A.search(text)
    thought = t.group(1).strip() if t else "(未解析到 Thought)"
    action = a.group(1).strip().splitlines()[0] if a else ""
    return thought, action

def run_tool(action):
    m = RE_TOOL.match(action.strip())
    if not m: return f"无法解析 Action「{action}」，请用 search[...]/calculate[...]/finish[...]", False
    name, arg = m.group(1).lower(), m.group(2).strip()
    if name == "finish": return arg, True
    if name not in TOOLS: return f"未知工具: {name}", False
    return TOOLS[name](arg), False

def build_messages(question, scratchpad):
    u = f"用户问题: {question}\n"
    u += f"\n--- 已有轨迹 ---\n{scratchpad}\n--- 请继续下一步 ---" if scratchpad else "\n请开始第一步（输出 Thought 和 Action）。"
    return [{"role": "system", "content": SYSTEM}, {"role": "user", "content": u}]

def run_react(question, think_fn):
    """ReAct 主循环：观察 → 思考 → 行动 → 再观察，直到 finish 或达上限。"""
    scratchpad = ""  # 累积轨迹，作为下一轮"观察"的上下文
    for step in range(1, MAX_STEPS + 1):
        print("\n" + "─" * 50)
        print(f"  步骤 {step}/{MAX_STEPS}")
        print("─" * 50)
        raw = think_fn(build_messages(question, scratchpad))   # 思考
        thought, action = parse_react(raw)
        print(f"Thought: {thought}")
        print(f"Action:  {action}")
        obs, done = run_tool(action)                           # 行动
        show = obs[:500] + ("..." if len(obs) > 500 else "")
        print(f"Observation: {show}")                          # 观察
        scratchpad += f"\nThought: {thought}\nAction: {action}\nObservation: {obs}\n"
        if done:
            print("\n" + "═" * 50)
            print(f"  最终答案: {obs}")
            print("═" * 50)
            return obs
    return "已达最大步数，请简化问题后重试。"

def _extract_expr(question):
    """从自然语言问题中提取数学表达式（demo 模式用）"""
    m = re.search(r"((?:sqrt\([^)]+\)|\d+\*\*\d+|[\d\.]+)\s*(?:[\+\-\*/]\s*(?:sqrt\([^)]+\)|\d+\*\*\d+|[\d\.]+))*)", question)
    return m.group(1).replace(" ", "") if m else "sqrt(144)+2**10"

def demo_think(messages):
    """无 API Key 时的规则驱动假 LLM，演示 ReAct 循环。"""
    user = messages[-1]["content"]
    qline = user.split("\n", 1)[0].replace("用户问题:", "").strip()

    if "--- 已有轨迹 ---" not in user:
        # 第一步：判断需要查资料还是直接计算
        needs_calc = bool(re.search(r"计算|乘以|\+|\-|\*|/|sqrt|\*\*", qline))
        needs_search = bool(re.search(r"是什么|什么是|多少|查|光速|谁|何时", qline))
        if needs_search and not re.search(r"^计算", qline):
            kw = qline
            for pat in ("是什么", "什么是", "请问", "查一下"):
                kw = kw.replace(pat, "")
            kw = kw.strip(" ？?，,") or "Python"
            return f"Thought: 需要查资料。\nAction: search[{kw}]"
        if needs_calc or re.search(r"\d", qline):
            expr = _extract_expr(qline)
            return f"Thought: 这是数学问题，先用计算器。\nAction: calculate[{expr}]"
        return f"Thought: 先搜索背景信息。\nAction: search[{qline}]"

    last_obs = user.split("Observation:")[-1].strip().split("\n")[0]
    did_search = "Action: search" in user
    did_calc = "Action: calculate" in user

    # 搜索后：若问题含「乘以 N」，用已知常量计算
    if did_search and not did_calc and re.search(r"乘以\s*\d+", qline):
        mul = re.search(r"乘以\s*(\d+)", qline)
        factor = mul.group(1) if mul else "60"
        if "光速" in qline or "299792458" in last_obs:
            return f"Thought: 查到光速，计算乘以{factor}。\nAction: calculate[299792458*{factor}]"
        nums = re.findall(r"\d[\d,\.]*", last_obs.replace(",", ""))
        base = nums[0] if nums else "1"
        return f"Thought: 查到数据 {base}，乘以{factor}。\nAction: calculate[{base}*{factor}]"

    if did_calc:
        return f"Thought: 计算完成，给出最终答案。\nAction: finish[{last_obs}]"
    if did_search:
        return f"Thought: 资料已够，汇总回答。\nAction: finish[{last_obs[:400]}]"
    return f"Thought: 结束。\nAction: finish[{last_obs}]"

def main():
    from config import resolve_llm_config, ENV_PATH, PROVIDERS

    p = argparse.ArgumentParser(description="ReAct CLI Agent（搜索 + 计算器）")
    p.add_argument("question", nargs="?", help="用户问题")
    p.add_argument("--demo", action="store_true", help="无 API Key 演示模式")
    p.add_argument("--provider", choices=list(PROVIDERS.keys()), help="LLM 服务商（也可在 .env 设 LLM_PROVIDER）")
    p.add_argument("--model", help="覆盖 .env 中的 OPENAI_MODEL")
    p.add_argument("--base-url", help="覆盖 .env 中的 OPENAI_BASE_URL")
    a = p.parse_args()
    q = a.question or input("请输入问题: ").strip()
    if not q: sys.exit("问题不能为空")
    print(f"\n问题: {q}\n")
    if a.demo:
        print("[Demo 模式 — 无需 API Key]\n")
        run_react(q, demo_think)
        return
    try:
        key, base_url, model = resolve_llm_config(a.provider)
    except RuntimeError as e:
        print(str(e))
        print(f"\n请复制 .env.example 为 .env 并填入 Key：")
        print(f"  copy {ENV_PATH.with_suffix('.example')} {ENV_PATH}")
        print("  或在 .env 中设置 OPENAI_API_KEY=sk-...\n")
        sys.exit(1)
    if a.model: model = a.model
    if a.base_url: base_url = a.base_url
    print(f"[LLM] provider={a.provider or 'from .env'} | model={model}")
    print(f"[LLM] base_url={base_url}\n")
    run_react(q, lambda m: call_llm(m, key, base_url, model))

if __name__ == "__main__":
    main()