"""
LLM Error Analysis Dashboard - Backend

This FastAPI service accepts reasoning traces in JSONL-compatible JSON form,
uses an LLM-as-Judge prompt to classify failure cases, and returns structured
analysis results for frontend visualization.
"""

import json
import os
from typing import Any, Dict, List, Literal, Optional

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from openai import OpenAI
from pydantic import BaseModel, Field

load_dotenv()

APP_NAME = "LLM Error Analysis Dashboard"
DEFAULT_MODEL = os.getenv("OPENAI_MODEL", "openai/gpt-5-mini")
MAX_FAILED_TRACE_CHARS = int(os.getenv("MAX_FAILED_TRACE_CHARS", "8000"))
MAX_CORRECT_TRACE_CHARS = int(os.getenv("MAX_CORRECT_TRACE_CHARS", "6000"))

client = OpenAI(
    api_key=os.environ.get("OPENAI_API_KEY"),
    base_url=os.environ.get("OPENAI_BASE_URL", "https://api.opensii.ai/"),
)

app = FastAPI(
    title=APP_NAME,
    description="Analyze and visualize reasoning errors in LLM trajectories.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ALLOW_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class AnalyzeRequest(BaseModel):
    items: List[Dict[str, Any]] = Field(..., description="Parsed JSONL records.")


class AnalyzeResult(BaseModel):
    id: str | int | None = None
    summary: str = ""
    category: str = ""
    category_name: str = ""
    reason: str = ""


class AnalyzeResponse(BaseModel):
    results: List[AnalyzeResult]
    total: int


class HealthResponse(BaseModel):
    status: Literal["ok"]
    app: str
    model: str
    has_api_key: bool


SYSTEM_PROMPT = """
你是一个严谨的软件工程错误分析助手，任务是阅读“模型推理轨迹”（含系统提示、用户问题、模型中间想法、最终答案等），
然后按照指定的错误类型体系，给出该条 case 的归因。

错误类型体系如下（只选一个你认为主导错误的类型）：

Category A：认知与理解偏差 (Cognitive & Understanding Gaps)
- A1 范围界定错误：修改范围不匹配；该修的没修，不该修的反而动了（例：本应全局修复却写了特例 hack）。
- A2 隐性约束忽视：忽略代码库中未明说但必须遵守的规则（如兼容性、结构不变式、性能）。
- A3 任务完成度不足：模型找到问题但只修了一半；缺少最终代码或关键步骤。

Category B：逻辑与实现缺陷 (Logic & Implementation Flaws)
- B1 边界条件处理不当：修复在正常输入有效，但在空值、负数、特殊类型等边界情况失败。
- B2 副作用引入：修复引入新的问题（如污染共享状态、警告爆炸、影响其他模块）。
- B3 错误的因果归因：虽然找到报错点，但误判根因，导致治标不治本。

Category C：验证与测试失效 (Verification Failures)
- C1 虚假成功：模型声称“测试通过”，但关键场景未覆盖或测试本身有误。
- C2 测试覆盖不足：只对单个 failing case 做修复，缺乏通用与边界测试。

输出时，请务必用 JSON 对象格式，字段如下：
{
  "summary": "用1-3句话，用自然语言总结该条推理和修复思路，以及哪里失败了",
  "category": "A1/A2/A3/B1/B2/B3/C1/C2 之一",
  "category_name": "中文名称，例如：范围界定错误",
  "reason": "详细解释为什么你选择这个类型（针对这条 case，而不是泛泛而谈）"
}
不要输出多余文字。
"""

NO_ERROR_PROMPT = """
你是一个推理一致性检查助手。给定一条模型推理轨迹（包含系统提示、用户问题、中间思考和最终答案）：

你的任务：
1. 判断推理过程中是否存在：
   - 自相矛盾（前后说法不一致）；
   - 中间步骤明显错误但后续没有纠正；
   - 最终结论与中间推理逻辑不一致。
2. 如果没有发现任何矛盾或明显错误，请输出（JSON）：
{
  "status": "no_error",
  "summary": "推理无错误",
  "reason": "推理过程前后一致，无明显矛盾或错误"
}
3. 如果发现问题，请输出（JSON）：
{
  "status": "has_issue",
  "summary": "简要描述发现的矛盾或问题",
  "reason": "详细说明矛盾发生在推理的哪些步骤，以及为什么认为它是错误或不一致"
}

只输出 JSON 对象，不要其他内容。
"""


def safe_json_loads(text: str) -> Dict[str, Any]:
    """Parse model output as JSON with a small fallback for accidental wrappers."""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            return json.loads(text[start : end + 1])
        raise


def truncate_trace(item: Dict[str, Any], max_chars: int) -> str:
    return json.dumps(item, ensure_ascii=False, indent=2)[:max_chars]


def call_llm(messages: List[Dict[str, str]]) -> Dict[str, Any]:
    response = client.chat.completions.create(
        model=DEFAULT_MODEL,
        messages=messages,
        response_format={"type": "json_object"},
    )
    content = response.choices[0].message.content or "{}"
    return safe_json_loads(content)


def analyze_correct_case(item: Dict[str, Any]) -> AnalyzeResult:
    data = call_llm(
        [
            {"role": "system", "content": NO_ERROR_PROMPT},
            {"role": "user", "content": truncate_trace(item, MAX_CORRECT_TRACE_CHARS)},
        ]
    )
    if data.get("status") == "no_error":
        return AnalyzeResult(
            id=item.get("id"),
            summary=data.get("summary", "推理无错误"),
            category="None",
            category_name="无错误",
            reason=data.get("reason", "推理过程前后一致，无明显矛盾或错误"),
        )
    return AnalyzeResult(
        id=item.get("id"),
        summary=data.get("summary", "推理存在矛盾或问题"),
        category="Inconsistency",
        category_name="推理矛盾",
        reason=data.get("reason", ""),
    )


def analyze_failed_case(item: Dict[str, Any]) -> AnalyzeResult:
    user_prompt = f"""
下面是一条模型推理轨迹的完整 JSON（已适当截断）：

{truncate_trace(item, MAX_FAILED_TRACE_CHARS)}

请根据上面的轨迹，分析：
1）模型大致在干什么；
2）最终为什么失败；
3）按照给定的错误分类体系，选出一个最合适的错误类型，并说明理由。

只按照系统提示要求输出 JSON 对象。
"""
    data = call_llm(
        [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]
    )
    return AnalyzeResult(
        id=item.get("id"),
        summary=data.get("summary", ""),
        category=data.get("category", ""),
        category_name=data.get("category_name", ""),
        reason=data.get("reason", ""),
    )


def call_llm_for_one_item(item: Dict[str, Any]) -> AnalyzeResult:
    if item.get("correct") is True:
        return analyze_correct_case(item)
    return analyze_failed_case(item)


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        app=APP_NAME,
        model=DEFAULT_MODEL,
        has_api_key=bool(os.environ.get("OPENAI_API_KEY")),
    )


@app.post("/analyze", response_model=AnalyzeResponse)
def analyze(req: AnalyzeRequest) -> AnalyzeResponse:
    results: List[AnalyzeResult] = []
    for item in req.items:
        try:
            results.append(call_llm_for_one_item(item))
        except Exception as exc:  # keep batch analysis robust
            results.append(
                AnalyzeResult(
                    id=item.get("id"),
                    summary="LLM 调用失败",
                    category="Error",
                    category_name="分析失败",
                    reason=f"调用出错：{exc}",
                )
            )
    return AnalyzeResponse(results=results, total=len(results))
