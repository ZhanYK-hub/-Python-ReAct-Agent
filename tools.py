"""
ReAct Agent 工具：搜索 + 计算器（纯 Python 标准库）
"""
import ast, json, math, operator, re, urllib.error, urllib.parse, urllib.request

_LOCAL_KB = {
    "python": "Python 是一种高级解释型编程语言，由 Guido van Rossum 于 1991 年发布。强调可读性，广泛用于 Web、数据科学、AI。",
    "光速": "真空中的光速约为 299792458 米/秒（约 3.0×10^8 m/s）。",
    "react": "ReAct（Reasoning + Acting）是一种 Agent 范式：交替进行推理（Thought）和工具调用（Action），根据观察（Observation）循环决策。",
    "agent": "AI Agent 是能感知环境、自主决策并调用工具完成目标的智能体。",
}

_BIN = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
        ast.Div: operator.truediv, ast.FloorDiv: operator.floordiv,
        ast.Mod: operator.mod, ast.Pow: operator.pow}
_UNARY = {ast.UAdd: operator.pos, ast.USub: operator.neg}
_FUNCS = {"abs": abs, "round": round, "min": min, "max": max,
          "sqrt": math.sqrt, "sin": math.sin, "cos": math.cos, "tan": math.tan,
          "log": math.log, "log10": math.log10, "pi": math.pi, "e": math.e}

def _eval(n):
    if isinstance(n, ast.Expression): return _eval(n.body)
    if isinstance(n, ast.Constant) and isinstance(n.value, (int, float)): return n.value
    if isinstance(n, ast.Num): return n.n
    if isinstance(n, ast.BinOp):
        op = _BIN.get(type(n.op))
        if not op: raise ValueError("unsupported operator")
        return op(_eval(n.left), _eval(n.right))
    if isinstance(n, ast.UnaryOp):
        op = _UNARY.get(type(n.op))
        if not op: raise ValueError("unsupported unary")
        return op(_eval(n.operand))
    if isinstance(n, ast.Call):
        if not isinstance(n.func, ast.Name): raise ValueError("bad call")
        name = n.func.id
        if name not in _FUNCS or name in ("pi", "e"): raise ValueError("bad function")
        return _FUNCS[name](*[_eval(a) for a in n.args])
    if isinstance(n, ast.Name) and n.id in ("pi", "e"): return _FUNCS[n.id]
    raise ValueError("invalid expression")

def calculate(expression: str) -> str:
    expr = expression.strip()
    if not expr: return "错误：表达式为空"
    try:
        r = _eval(ast.parse(expr, mode="eval"))
        if isinstance(r, float) and r.is_integer(): r = int(r)
        return str(r)
    except Exception as e: return f"计算错误: {e}"

def _local_search(q):
    q_lower = q.lower()
    for key, val in _LOCAL_KB.items():
        if key in q_lower or key in q:
            return f"[本地知识库] {val}"
    return ""

def _get(url, timeout=5):
    req = urllib.request.Request(url, headers={"User-Agent": "ReActAgent/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="replace")

def _ddg(q):
    url = "https://api.duckduckgo.com/?" + urllib.parse.urlencode({"q": q, "format": "json", "no_html": 1})
    try: data = json.loads(_get(url, timeout=5))
    except Exception: return ""
    parts = []
    if data.get("AbstractText"): parts.append(data["AbstractText"])
    if data.get("Answer"): parts.append("直接答案: " + str(data["Answer"]))
    for t in data.get("RelatedTopics", [])[:3]:
        if isinstance(t, dict) and t.get("Text"): parts.append(t["Text"])
    return "\n".join(parts)

def _wiki(q, lang="zh"):
    url = f"https://{lang}.wikipedia.org/w/api.php?" + urllib.parse.urlencode({
        "action": "query", "list": "search", "srsearch": q, "format": "json", "utf8": 1,
    })
    try:
        hits = json.loads(_get(url, timeout=5)).get("query", {}).get("search", [])
        if not hits: return ""
        h = hits[0]
        sn = re.sub(r"<[^>]+>", "", h.get("snippet", ""))
        return f"维基百科({lang})《{h['title']}》: {sn}..."
    except Exception: return ""

def search(query: str) -> str:
    query = query.strip()
    if not query: return "错误：搜索词为空"
    local = _local_search(query)
    if local: return local
    for fn in (_ddg, lambda x: _wiki(x, "zh"), lambda x: _wiki(x, "en")):
        out = fn(query)
        if out: return out
    return f"未找到「{query}」相关资料（可换关键词或改用 calculate）"

TOOLS = {"search": search, "calculate": calculate}