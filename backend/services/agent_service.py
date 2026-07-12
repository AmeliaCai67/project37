"""
Agent Service - ReAct Agent 核心逻辑
实现 Thought → Action → Observation → Answer 循环
"""
import json
import re
from typing import List, Dict, Any, Optional, AsyncGenerator
from pathlib import Path
from datetime import datetime

from core.llm_client import llm_client
from core.tools import GlobTool, ReadTool, GrepTool, StatTool, ExecTool
from core.sandbox import RestrictedPythonSandbox
from core.logging import get_logger

logger = get_logger(__name__)


class AgentService:
    """ReAct Agent 服务"""
    
    MAX_ITERATIONS = 8
    CONTEXT_LIMIT = 15000
    
    def __init__(self, working_dir: Path = None, output_dir: Path = None):
        self.working_dir = Path(working_dir) if working_dir else Path(".")
        self.output_dir = Path(output_dir) if output_dir else None
        self.llm_client = llm_client
        
        # 初始化工具
        self.tools = {
            "glob": GlobTool(working_dir=self.working_dir),
            "read": ReadTool(working_dir=self.working_dir),
            "grep": GrepTool(working_dir=self.working_dir),
            "stat": StatTool(working_dir=self.working_dir),
            "exec": ExecTool(working_dir=self.working_dir, output_dir=self.output_dir),
        }
    
    def _build_system_prompt(self, role: str, file_names: List[str] = None, file_contents: Dict[str, str] = None) -> str:
        """
        构建系统提示

        根据用户权限角色生成不同的提示：
        - user: 不包含 glob 工具，只能读取指定文件
        - admin: 包含 glob 工具，可以自主探索所有文件
        """
        file_names = file_names or []
        file_contents = file_contents or {}

        # 基础提示
        base_prompt = """你是一个智能数据分析助手，必须严格使用 ReAct (Reasoning + Acting) 模式帮助用户分析文件数据。

**核心原则**：在没有使用工具查看文件之前，你绝对不允许直接给出答案。禁止根据训练数据猜测文件内容。

你的工作流程是:
1. Thought: 分析用户问题，思考需要什么信息
2. Action: 选择合适的工具获取信息（必须使用工具）
3. Observation: 观察工具返回的结果
4. 重复 1-3 直到有足够信息
5. Answer: 给出最终答案

你可以使用以下工具:
"""

        # 如果文件内容已预加载，添加提示
        preload_hint = ""
        if file_contents:
            preload_hint = "\n**重要提示**：所选文件的内容已经提供在对话上下文中（见下方用户消息）。如果数据已在上下文中，请直接使用 exec 工具进行数据分析，无需再用 read/stat 工具重复读取文件。只有在需要查看未提供内容的文件时，才使用 read 工具。\n"
        
        if role == "user":
            # 只读用户：只能读取指定文件，不能使用 glob
            prompt = base_prompt + """
- read: 读取文件内容
  参数: {"path": "文件名", "offset": 0, "limit": 100}
  
- grep: 在文件中搜索关键词
  参数: {"pattern": "搜索词", "path": "文件名", "context": 0}
  
- stat: 获取文件信息
  参数: {"path": "文件名"}

用户已选择以下文件可供分析："""
            if file_names:
                for name in file_names:
                    prompt += f"\n- {name}"
            if file_contents:
                prompt += "\n\n请基于这些文件回答用户问题。\n**注意**：文件内容已在对话上下文中提供，请直接基于上下文中的数据进行回答或使用 exec 工具进行数据分析。"
            else:
                prompt += "\n\n请基于这些文件回答用户问题。\n**注意**：你必须先使用 read 或 stat 工具读取文件内容，不能直接猜测答案。"
            
        else:
            # 管理员：可以使用所有工具自主探索
            prompt = base_prompt + """
- glob: 列出匹配的文件
  参数: {"pattern": "*.csv"}
  
- read: 读取文件内容
  参数: {"path": "文件名", "offset": 0, "limit": 100}
  
- grep: 在文件中搜索关键词
  参数: {"pattern": "搜索词", "path": "文件名", "context": 0}
  
- stat: 获取文件信息
  参数: {"path": "文件名"}
  
- exec: 执行 Python 代码进行数据分析
  参数: {"command": "python代码", "type": "python"}

**exec 沙箱中可用的 Python 库：**
- pandas (含 read_csv/read_excel)、numpy、matplotlib、scipy、scikit-learn
- openpyxl (Excel 读写)、csv、json、re、datetime、math、statistics
- itertools、collections、functools、decimal、fractions、random
- 如有需要，可用 pip 安装其他纯 Python 包
  
你可以访问用户的所有文件。请根据需要使用 glob 发现文件，然后使用其他工具进行分析。
"""
        
        prompt += preload_hint

        prompt += """
输出格式示例：

**第一步（发现/读取文件）：**
Thought: 我需要先查看有哪些文件
Action: glob
Action Input: {"pattern": "*.csv"}

**后续步骤（分析）：**
Thought: 让我读取文件的前几行了解结构
Action: read
Action Input: {"path": "文件名.csv", "offset": 0, "limit": 10}

**最终步骤：**
Thought: 现在我已经有足够的信息来回答
Answer: 根据数据分析，...

重要规则:
- **格式强制**：每条回复必须以 Thought: 开头，然后包含 Action: + Action Input: 或 Answer:。不得输出无前缀的自由文本。
- 在没有使用工具查看文件前，绝对禁止直接给出 Answer
- 如果文件很大，先使用 stat 了解结构，再使用 read 分页读取
- 对于复杂分析，使用 exec 工具编写 Python 代码
- 回答要具体，引用数据支撑你的结论
- **停止条件**：如果你已经获得足够信息来回答用户的问题，必须立即停止调用工具，直接给出 Answer。不要过度分析或追求额外数据。
- **输出规范**：禁止在回答中使用任何 emoji 表情符号（如 ✅❌📊📈等），请使用纯文本格式。
- **文件保护**：你只能读取工作目录中的文件，禁止修改、删除或覆盖任何源文件。
- **输出目录**：所有输出文件（图表、报告、CSV 结果）必须保存到 /output/ 目录下。如果用户没有要求保存，你也应该把有价值的交付物自动保存到 /output/。
"""
        return prompt
    
    def _parse_llm_response(self, content: str) -> Dict[str, Any]:
        """解析 LLM 响应，提取 Thought, Action, Answer"""
        result = {
            "thought": "",
            "action": None,
            "action_input": None,
            "answer": None
        }

        # 提取最后一个 Action（优先于 Answer，避免 LLM 把历史 Answer 混进来）
        action_matches = re.findall(r'Action:\s*(\w+)', content)
        if action_matches:
            result["action"] = action_matches[-1].strip()

        # 提取 Thought：取最后一个 Thought 块
        thought_parts = re.findall(r'Thought:\s*(.+?)(?=\n(?:Action|Answer):|$)', content, re.DOTALL)
        if thought_parts:
            result["thought"] = thought_parts[-1].strip()

        # 提取 Action Input：取最后一个 Action Input
        if result["action"]:
            action_inputs = re.findall(r'Action Input:\s*(\{[^}]+\}|.+?)(?=\n(?:Thought|Action|Answer):|$)', content, re.DOTALL)
            if action_inputs:
                input_str = action_inputs[-1].strip()
                try:
                    result["action_input"] = json.loads(input_str)
                except json.JSONDecodeError:
                    result["action_input"] = {"command": input_str} if result["action"] == "exec" else {"path": input_str}

        # 提取 Answer：只有没有 Action 时才提取（防止 LLM 编造的多轮历史里混入旧 Answer）
        if not result["action"]:
            answer_match = re.search(r'Answer:\s*(.+)', content, re.DOTALL)
            if answer_match:
                result["answer"] = answer_match.group(1).strip()

        logger.debug(f"解析 LLM 响应: thought={result['thought'][:50] if result['thought'] else ''}..., action={result['action']}, has_answer={bool(result['answer'])}")
        return result
    
    def _execute_tool(self, tool_name: str, tool_input: Dict) -> Dict[str, Any]:
        """执行工具"""
        if tool_name not in self.tools:
            return {"success": False, "error": f"未知工具: {tool_name}"}
        
        tool = self.tools[tool_name]
        try:
            result = tool.execute(**tool_input)
            return result
        except Exception as e:
            logger.error(f"工具执行错误: {tool_name} - {e}")
            return {"success": False, "error": str(e)}
    
    def _compress_context(self, steps: List[Dict]) -> List[Dict]:
        """
        上下文压缩
        当历史步骤过长时，对早期步骤进行摘要，保留最近步骤的完整信息
        """
        if len(steps) <= 5:
            return steps
        
        # 保留最近 3 个完整步骤
        recent_steps = steps[-3:]
        
        # 对早期步骤进行摘要
        early_steps = steps[:-3]
        summary = {
            "type": "summary",
            "step_count": len(early_steps),
            "summary": f"前面执行了 {len(early_steps)} 步: " + 
                      " → ".join([s.get("action", "思考") for s in early_steps])
        }
        
        return [summary] + recent_steps
    
    def _truncate_observation(self, content: str, max_length: int = 500) -> str:
        """截断观察结果，避免过长"""
        if len(content) <= max_length:
            return content
        
        return content[:max_length] + "\n[内容已截断]"
    
    def _has_files(self) -> bool:
        """检查工作目录下是否有文件"""
        try:
            return any(p.is_file() for p in self.working_dir.iterdir())
        except Exception:
            return False
    
    async def _run_loop(
        self,
        user,
        message: str,
        file_names: List[str] = None,
        file_contents: Dict[str, str] = None,
        history: List[Dict[str, str]] = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        共享 Agent 循环 - 运行 Thought→Action→Observation 直到得出结论。
        同时用于 run() 和 run_stream()，消除重复代码。

        Args:
            history: 前几轮对话的 user/assistant 消息对，按时间顺序排列
                     [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}, ...]

        Yields:
            step dicts: {"type": "thought"|"action"|"observation"|"final"|"error"|"system", ...}
            最后一个 yielded step 的 type 为 "final" 或 "error"。
        """
        file_names = file_names or []
        file_contents = file_contents or {}
        history = history or []
        total_tokens = 0
        tool_executed = False
        direct_answer_rejects = 0
        format_errors = 0

        # 构建初始消息
        system_prompt = self._build_system_prompt(user.role, file_names, file_contents)
        messages = [{"role": "system", "content": system_prompt}]

        # 注入对话历史（前几轮的 user/assistant 问答对）
        if history:
            history_chars = 0
            for h in history:
                messages.append({"role": h["role"], "content": h["content"]})
                history_chars += len(h["content"])
            logger.info(f"[Agent] 注入对话历史 | pairs={len(history) // 2} | chars={history_chars}")

        if file_contents:
            context_parts = ["以下是你需要分析的文件内容（已预加载，无需再次读取）：\n"]
            for fname, text in file_contents.items():
                if text:
                    context_parts.append(f"=== 文件: {fname} ===\n{text}")
            messages.append({"role": "user", "content": "\n\n".join(context_parts)})

        messages.append({"role": "user", "content": message})

        # 上下文预算保护：超限时从最旧的历史开始丢弃
        context_length = sum(len(m["content"]) for m in messages)
        if context_length > self.CONTEXT_LIMIT and history:
            # 保留 system + 当前消息 + file_contents 的最小集合
            core_messages = [messages[0]]  # system
            history_msgs = messages[1:1 + len(history)]
            rest_msgs = messages[1 + len(history):]  # file_contents + current message
            core_len = len(messages[0]["content"]) + sum(len(m["content"]) for m in rest_msgs)
            budget = self.CONTEXT_LIMIT - core_len

            trimmed_history = []
            # 从最新的历史开始保留（倒序），直到预算耗尽
            for h in reversed(history_msgs):
                if budget <= 0:
                    break
                if len(h["content"]) <= budget:
                    trimmed_history.insert(0, h)
                    budget -= len(h["content"])
                else:
                    # 截断单条消息以适配剩余空间
                    truncated = {"role": h["role"], "content": h["content"][:budget] + "..."}
                    trimmed_history.insert(0, truncated)
                    budget = 0

            messages = [messages[0]] + trimmed_history + rest_msgs
            logger.info(f"[Agent] 上下文预算保护 | 历史从 {len(history)} 条裁剪为 {len(trimmed_history)} 条")

        logger.info(f"[Agent] 开始 run | user={user.username} | role={user.role} | file_names={file_names} | working_dir={self.working_dir}")

        iteration = 0
        while iteration < self.MAX_ITERATIONS:
            iteration += 1
            try:
                logger.info(f"[Agent] 第 {iteration} 轮调用 LLM...")
                response = await self.llm_client.chat_completion(messages)
                content = response["choices"][0]["message"]["content"]
                tokens_used = response.get("usage", {}).get("total_tokens", 0)
                total_tokens += tokens_used
                logger.info(f"[Agent] LLM 返回 | tokens_used={tokens_used} | content_preview={content[:200].replace(chr(10), ' ')}")

                parsed = self._parse_llm_response(content)
                logger.info(f"[Agent] 解析结果 | thought={bool(parsed['thought'])} | action={parsed['action']} | has_answer={bool(parsed['answer'])}")

                # 幻觉 guard：未使用工具前禁止直接回答（有预加载文件内容时跳过）
                if parsed["answer"] and not tool_executed and not file_contents and (file_names or self._has_files()):
                    direct_answer_rejects += 1
                    logger.warning(f"[Agent] 幻觉 guard 触发 | direct_answer_rejects={direct_answer_rejects}")
                    if direct_answer_rejects >= 2:
                        logger.error("[Agent] 连续两次直接回答，终止流程")
                        yield {
                            "type": "error",
                            "content": "AI 未能正确分析文件。请尝试更具体地描述你的问题，或重新上传文件后重试。",
                            "iteration": iteration,
                            "_tokens_used": total_tokens,
                        }
                        return
                    yield {
                        "type": "system",
                        "content": "[系统纠正] AI 尝试直接回答，但未使用工具查看文件。已强制要求先使用工具。",
                        "iteration": iteration,
                    }
                    correction = "你还没有使用任何工具查看文件内容。请严格遵守 ReAct 模式：必须先使用 glob/read/stat/exec 等工具读取并分析文件，然后才能给出 Answer。禁止根据训练数据猜测答案。"
                    messages.append({"role": "assistant", "content": content})
                    messages.append({"role": "user", "content": correction})
                    continue

                # 最终答案
                if parsed["answer"]:
                    logger.info("[Agent] 生成最终答案，结束")
                    yield {
                        "type": "final",
                        "thought": parsed["thought"],
                        "answer": parsed["answer"],
                        "iteration": iteration,
                        "_tokens_used": total_tokens,
                    }
                    return

                # 工具执行
                if parsed["action"]:
                    tool_executed = True
                    if parsed["thought"]:
                        yield {
                            "type": "thought",
                            "iteration": iteration,
                            "content": parsed["thought"],
                        }

                    yield {
                        "type": "action",
                        "iteration": iteration,
                        "action": parsed["action"],
                        "input": parsed["action_input"],
                    }

                    logger.info(f"[Agent] 执行工具 | tool={parsed['action']} | input={parsed['action_input']}")
                    observation = self._execute_tool(
                        parsed["action"],
                        parsed["action_input"] or {}
                    )
                    logger.info(f"[Agent] 工具返回 | success={observation.get('success', True)} | observation_preview={str(observation)[:200]}")

                    yield {
                        "type": "observation",
                        "iteration": iteration,
                        "tool": parsed["action"],
                        "content": observation,
                        "success": observation.get("success", True),
                    }

                    # 截断过长的 observation（错误时保留关键字段）
                    if observation.get("error"):
                        obs_for_llm = {
                            "success": observation.get("success"),
                            "error": observation.get("error"),
                            "error_type": observation.get("error_type"),
                            "code": observation.get("code"),
                            "stdout": observation.get("stdout", ""),
                            "stderr": self._truncate_observation(
                                observation.get("stderr", ""), max_length=1000
                            ),
                        }
                        observation_content = json.dumps(obs_for_llm, ensure_ascii=False)
                    else:
                        observation_content = json.dumps(observation, ensure_ascii=False)
                        if len(observation_content) > 2000:
                            observation_content = observation_content[:2000] + "...[已截断]"

                    # 接近上限时添加强制停止提示
                    remaining = self.MAX_ITERATIONS - iteration
                    if remaining <= 2:
                        observation_content += f"\n[警告] 仅剩 {remaining} 轮迭代机会，必须在下一条消息中直接给出最终 Answer，禁止继续调用工具。"
                    else:
                        observation_content += "\n[若已获得关键数据，请直接给出最终答案，不要继续调用工具]"

                    assistant_msg = f"Thought: {parsed['thought']}\n"
                    assistant_msg += f"Action: {parsed['action']}\n"
                    assistant_msg += f"Action Input: {json.dumps(parsed['action_input'], ensure_ascii=False)}"

                    messages.append({"role": "assistant", "content": assistant_msg})
                    messages.append({"role": "user", "content": f"Observation: {observation_content}"})

                    # 上下文压缩（摘要式）
                    context_length = sum(len(m["content"]) for m in messages)
                    if context_length > self.CONTEXT_LIMIT:
                        logger.info(f"[Agent] 上下文过长 ({context_length})，进行摘要式压缩")
                        compressed = [messages[0], messages[1]]
                        middle = messages[2:-4]
                        if middle:
                            summary_parts = []
                            for i in range(0, len(middle), 2):
                                if i < len(middle):
                                    am = middle[i].get("content", "")
                                    action_hist = re.search(r'Action:\s*(\w+)', am)
                                    action_hist = action_hist.group(1) if action_hist else "unknown"
                                    if i + 1 < len(middle):
                                        om = middle[i+1].get("content", "")
                                        sh = "成功" if '"success": true' in om or '"success": True' in om else "失败"
                                        summary_parts.append(f"{action_hist}({sh})")
                                    else:
                                        summary_parts.append(f"{action_hist}")
                            summary_content = "历史操作摘要：已完成 " + " → ".join(summary_parts) + "。以上步骤已获取足够数据，请基于已有信息直接给出最终答案，不要继续调用工具。"
                            compressed.append({"role": "user", "content": summary_content})
                        compressed.extend(messages[-4:])
                        messages = compressed
                else:
                    # 格式纠正
                    format_errors += 1
                    if format_errors >= 2:
                        logger.error(f"[Agent] 连续 {format_errors} 次格式错误，终止流程")
                        yield {
                            "type": "error",
                            "content": "AI 响应格式不正确，已重试但未修复",
                            "raw_response": content,
                            "iteration": iteration,
                            "_tokens_used": total_tokens,
                        }
                        return
                    logger.warning(f"[Agent] 格式纠正第 {format_errors} 次 | raw={content[:300]}")
                    yield {
                        "type": "system",
                        "content": "[系统纠正] AI 响应格式不正确，已要求按规范格式重新输出。",
                        "iteration": iteration,
                    }
                    correction = "你的回复格式不正确。请严格按照以下格式输出：\n\nThought: <你的思考>\nAction: <工具名>\nAction Input: {\"参数\": \"值\"}\n\n或：\n\nThought: <你的思考>\nAnswer: <最终答案>\n\n请基于已有信息重新输出。"
                    messages.append({"role": "assistant", "content": content})
                    messages.append({"role": "user", "content": correction})
                    continue

            except Exception as e:
                logger.error(f"[Agent] 执行错误: {e}", exc_info=True)
                yield {
                    "type": "error",
                    "content": str(e),
                    "iteration": iteration,
                    "_tokens_used": total_tokens,
                }
                return

        # 达到最大迭代次数
        logger.error("[Agent] 达到最大迭代次数")
        yield {
            "type": "error",
            "content": "分析过程过长，请尝试更具体的问题。",
            "iteration": iteration,
            "_tokens_used": total_tokens,
        }

    async def run(
        self,
        user,
        message: str,
        file_names: List[str] = None,
        file_contents: Dict[str, str] = None,
        history: List[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """
        运行 Agent（非流式） - 收集所有步骤后返回完整结果。
        """
        steps = []
        final_answer = ""
        final_tokens = 0
        success = True

        async for step in self._run_loop(user, message, file_names, file_contents, history):
            tokens = step.pop("_tokens_used", None)
            if tokens is not None:
                final_tokens = tokens

            if step.get("type") == "final":
                final_answer = step.get("answer", "")
                steps.append(step)
                success = True
            elif step.get("type") == "error":
                final_answer = step.get("content", "")
                steps.append(step)
                success = False
            else:
                steps.append(step)

        return {
            "success": success,
            "answer": final_answer,
            "steps": steps,
            "tokens_used": final_tokens,
        }
    
    async def _stream_steps(self, steps: List[Dict]) -> AsyncGenerator[str, None]:
        """
        将步骤转换为 SSE 格式流式输出
        
        Yields:
            str: SSE 格式数据，如 'data: {"type": "thought", ...}\n\n'
        """
        for step in steps:
            step_type = step.get("type", "unknown")
            
            if step_type == "final" or step_type == "answer":
                # 最终答案
                data = {
                    "type": "answer",
                    "content": step.get("answer", step.get("content", "")),
                    "thought": step.get("thought", "")
                }
                yield f'data: {json.dumps(data, ensure_ascii=False)}\n\n'
                
            elif step_type == "thought":
                # 思考
                data = {
                    "type": "thought",
                    "content": step.get("content", "")
                }
                yield f'data: {json.dumps(data, ensure_ascii=False)}\n\n'
                
            elif step_type == "action":
                # 行动 - 支持 'action' 或 'tool' 键
                data = {
                    "type": "action",
                    "tool": step.get("tool") or step.get("action", ""),
                    "input": step.get("input", {})
                }
                yield f'data: {json.dumps(data, ensure_ascii=False)}\n\n'
                
            elif step_type == "observation":
                # 观察结果
                content = step.get("content", {})
                # 提取可读的观察内容
                if isinstance(content, dict):
                    # 错误结果：优先展示错误信息 + 执行的代码
                    if content.get("error"):
                        err_type = content.get("error_type", "错误")
                        code = content.get("code", "")
                        stderr = content.get("stderr", "")
                        stdout = content.get("stdout", "")
                        parts = [f"[{err_type}] {content['error']}"]
                        if code:
                            parts.append(f"执行的代码:\n```python\n{code}\n```")
                        if stdout:
                            parts.append(f"标准输出:\n{stdout}")
                        if stderr:
                            parts.append(f"标准错误:\n{stderr}")
                        display_content = "\n\n".join(parts)
                    else:
                        display_content = (content.get("output") or
                                         content.get("files") or
                                         content.get("lines") or
                                         content.get("content") or
                                         content.get("matches") or
                                         str(content))
                else:
                    display_content = str(content)
                    
                data = {
                    "type": "observation",
                    "tool": step.get("tool", step.get("action", "")),
                    "content": display_content,
                    "success": step.get("success", True)
                }
                # 如果有错误信息，添加到输出
                if step.get("error"):
                    data["error"] = step["error"]
                yield f'data: {json.dumps(data, ensure_ascii=False)}\n\n'
                
            elif step_type == "error":
                data = {
                    "type": "error",
                    "content": step.get("content", "")
                }
                yield f'data: {json.dumps(data, ensure_ascii=False)}\n\n'
            
            elif step_type == "system":
                data = {
                    "type": "system",
                    "content": step.get("content", "")
                }
                yield f'data: {json.dumps(data, ensure_ascii=False)}\n\n'
            
            elif step_type == "summary":
                data = {
                    "type": "summary",
                    "content": step.get("summary", "")
                }
                if step.get("step_count"):
                    data["step_count"] = step["step_count"]
                yield f'data: {json.dumps(data, ensure_ascii=False)}\n\n'
            
            elif step_type == "metadata":
                data = {
                    "type": "metadata",
                    "tokens_used": step.get("tokens_used", 0),
                    "steps_count": step.get("steps_count", 0)
                }
                yield f'data: {json.dumps(data, ensure_ascii=False)}\n\n'
            
            elif step_type == "done":
                # 结束标记 - 产生特殊标记
                yield "data: [DONE]\n\n"
    
    async def run_stream(
        self,
        user,
        message: str,
        file_names: List[str] = None,
        file_contents: Dict[str, str] = None,
        history: List[Dict[str, str]] = None,
    ) -> AsyncGenerator[str, None]:
        """
        流式运行 Agent - 每完成一个步骤就实时推送 SSE 事件。
        """
        async for step in self._run_loop(user, message, file_names, file_contents, history):
            step.pop("_tokens_used", None)
            async for event in self._stream_steps([step]):
                yield event
        yield "data: [DONE]\n\n"
