# LLM Error Analysis Dashboard

一个面向大模型推理轨迹的 **错误归因与可视化分析平台**。项目支持上传 JSONL 推理轨迹，调用 LLM-as-Judge 自动分析错误原因，并在网页端完成错误分布统计、case 筛选、推理 timeline 回放与 CSV 导出。

## 项目亮点

- **端到端分析 pipeline**：JSONL 输入 → FastAPI 后端 → LLM 自动归因 → Web Dashboard 可视化。
- **细粒度错误分类体系**：将失败轨迹划分为 A/B/C 三大类和 8 个子类，覆盖理解偏差、实现缺陷与验证失效。
- **正确轨迹一致性检查**：对 `correct=true` 的轨迹额外检测推理前后是否自相矛盾。
- **交互式可视化界面**：支持错误占比图、细分类柱状图、关键词搜索、类别过滤、timeline 查看与 CSV 导出。
- **安全工程化配置**：使用 `.env.example` 管理环境变量，`.gitignore` 默认忽略真实 API key。

## 项目结构

```text
llm-error-analysis-dashboard-upgraded/
├── backend/
│   ├── app.py              # FastAPI 后端与 LLM-as-Judge 逻辑
│   ├── requirements.txt    # Python 依赖
│   └── test_api.py         # API 连通性测试
├── frontend/
│   └── index.html          # 前端 Dashboard
├── data/
│   └── sample.jsonl        # 示例输入
├── docs/
│   └── error_taxonomy.md   # 错误分类体系说明
├── scripts/
│   └── run_backend.sh      # 后端启动脚本
├── .env.example
├── .gitignore
├── LICENSE
└── README.md
```

## 快速开始

### 1. 创建环境

```bash
conda create -n llm-web python=3.10
conda activate llm-web
pip install -r backend/requirements.txt
```

### 2. 配置环境变量

复制示例配置：

```bash
cp .env.example .env
```

然后编辑 `.env`：

```text
OPENAI_API_KEY=your_api_key_here
OPENAI_BASE_URL=https://api.opensii.ai/
OPENAI_MODEL=openai/gpt-5-mini
```

> 注意：不要把真实 `.env` 上传到 GitHub。

### 3. 测试 API 连通性

```bash
python backend/test_api.py
```

### 4. 启动后端

```bash
uvicorn backend.app:app --reload --host 127.0.0.1 --port 8000
```

或者：

```bash
bash scripts/run_backend.sh
```

### 5. 打开前端

直接用浏览器打开：

```text
frontend/index.html
```

默认后端地址为：

```text
http://127.0.0.1:8000
```

## 输入格式

输入文件为 JSONL，每一行是一条推理轨迹：

```json
{"id":"case-001","correct":false,"model_data":{"messages":[{"role":"user","content":"..."},{"role":"assistant","content":"..."}]}}
```

其中：

- `id`：case 编号
- `correct`：该轨迹最终是否正确
- `model_data.messages` / `model_data.fncall_messages`：推理过程消息

## 错误分类体系

### Category A：认知与理解偏差

- A1 范围界定错误
- A2 隐性约束忽视
- A3 任务完成度不足

### Category B：逻辑与实现缺陷

- B1 边界条件处理不当
- B2 副作用引入
- B3 错误的因果归因

### Category C：验证与测试失效

- C1 虚假成功
- C2 测试覆盖不足

此外，对于正确轨迹：

- `None`：未发现明显推理错误
- `Inconsistency`：正确轨迹中存在推理矛盾


