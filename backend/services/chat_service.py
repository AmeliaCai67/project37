from typing import List, Dict, Optional
from pathlib import Path
from datetime import datetime
import json

from sqlalchemy.orm import Session

from models.conversation import Conversation, MessageRole
from models.user import User
from models.workspace import Workspace
from services.conversation_service import ConversationService
from services.file_service import FileService
from services.workspace_service import WorkspaceService
from services.agent_service import AgentService
from services.output_artifact_service import OutputArtifactService
from core.llm_client import llm_client
from core.logging import get_logger

logger = get_logger(__name__)


class ChatService:
    """聊天服务 - ReAct Agent 模式"""

    HISTORY_MAX_PAIRS = 5          # 最多保留的历史问答对数
    HISTORY_MAX_ANSWER_CHARS = 500  # 每条历史回答的最大字符数

    @staticmethod
    def _replace_sandbox_paths(text: str, output_dir: str) -> str:
        """把答案中残留的 /sandbox_output 虚拟路径替换为真实输出路径（双保险，
        系统提示词已禁止 LLM 提及该前缀）。"""
        if not text or "/sandbox_output" not in text:
            return text or ""
        base = output_dir.rstrip("/")
        return text.replace("/sandbox_output/", f"{base}/").replace(
            "/sandbox_output", base
        )

    @staticmethod
    def _save_answer_markdown(output_dir: str, question: str, answer: str) -> Optional[Path]:
        """把本次问答以 Markdown 写入输出目录（回答本身也是交付物），
        并附上当前输出目录中的产物清单。失败不阻塞主流程。"""
        try:
            out = Path(output_dir)
            out.mkdir(parents=True, exist_ok=True)
            now = datetime.now()
            artifacts = [
                p.name for p in sorted(out.iterdir())
                if p.is_file() and not p.name.startswith("回答_") and not p.name.startswith(".")
            ]
            lines = [
                "# 问数回答",
                "",
                f"- 时间：{now.strftime('%Y-%m-%d %H:%M:%S')}",
                f"- 问题：{question}",
                "",
                "---",
                "",
                answer or "（未生成回答）",
            ]
            if artifacts:
                lines += ["", "---", "", "## 产物清单", ""]
                lines += [f"- {name}" for name in artifacts]
            md_path = out / f"回答_{now.strftime('%Y%m%d_%H%M%S')}.md"
            md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
            return md_path
        except Exception:
            logger.warning("Failed to save answer markdown", exc_info=True)
            return None

    @staticmethod
    def _resolve_file_names(db: Session, file_ids: List[int], user_id: int) -> List[str]:
        """将文件 ID 列表解析为实际存储的文件名列表"""
        names = []
        if not file_ids:
            return names
        for fid in file_ids:
            f = FileService.get_by_id(db, fid)
            if f and f.owner_id == user_id:
                names.append(f.filename)
        return names

    @staticmethod
    def _extract_file_contents(db: Session, file_ids: List[int], user_id: int) -> dict:
        """提取预加载的文件内容，key 为文件名，value 为提取的文本"""
        contents = {}
        if not file_ids:
            return contents
        for fid in file_ids:
            f = FileService.get_by_id(db, fid)
            if f and f.owner_id == user_id and f.extracted_text:
                contents[f.filename] = f.extracted_text
        return contents

    @staticmethod
    def _build_conversation_history(
        db: Session, conversation_id: int, max_pairs: int = None
    ) -> List[Dict[str, str]]:
        """
        构建对话历史，返回原生 chat 格式的 user/assistant 消息对列表。

        只取最近 N 对成功的问答，assistant 回答截断以控制上下文长度。
        返回 [] 表示无历史（新对话或此前无成功交换）。
        """
        if not conversation_id:
            return []

        max_pairs = max_pairs or ChatService.HISTORY_MAX_PAIRS

        all_messages = ConversationService.get_messages(db, conversation_id)
        if not all_messages:
            return []

        # 按时间排序（get_messages 已排序，但确保一下），只取 user + assistant
        chat_messages = [m for m in all_messages if m.role in (MessageRole.USER, MessageRole.ASSISTANT)]

        # 从尾部开始，成对提取 user→assistant 交换
        pairs = []
        i = len(chat_messages) - 1
        while i >= 0 and len(pairs) < max_pairs:
            assistant_msg = None
            user_msg = None

            # 找最近的 assistant 消息
            if chat_messages[i].role == MessageRole.ASSISTANT:
                assistant_msg = chat_messages[i]
                i -= 1
            else:
                i -= 1
                continue

            # 找该 assistant 对应的 user 消息
            if i >= 0 and chat_messages[i].role == MessageRole.USER:
                user_msg = chat_messages[i]
                i -= 1
            else:
                continue  # 不成对，跳过

            # 截断过长的回答
            answer_text = assistant_msg.content
            if len(answer_text) > ChatService.HISTORY_MAX_ANSWER_CHARS:
                answer_text = answer_text[:ChatService.HISTORY_MAX_ANSWER_CHARS] + "..."

            pairs.insert(0, (
                {"role": "user", "content": user_msg.content},
                {"role": "assistant", "content": answer_text},
            ))

        # 展平为消息列表
        history = []
        for u, a in pairs:
            history.append(u)
            history.append(a)

        return history

    @staticmethod
    def _resolve_workspace_and_dirs(db: Session, user: User, workspace_id: Optional[int] = None):
        """解析工作空间并返回 working_dir / output_dir"""
        if workspace_id:
            ws = db.query(Workspace).filter_by(id=workspace_id, owner_id=user.id).first()
            if not ws:
                raise ValueError("Workspace not found")
        else:
            ws = WorkspaceService.get_or_create_internal(db, user)

        if ws.type == "external":
            # Copy isolation: agent works on internal copy
            copy_dir = WorkspaceService.get_internal_copy_dir(user.id, ws.id)
            # 同步 + 增量登记 File 记录（源目录新增的文件也会出现在【文件】页）
            WorkspaceService.sync_and_register(db, user, ws)
            working_dir = str(copy_dir)
        else:
            working_dir = str(FileService._get_user_dir(user.id))

        output_dir = OutputArtifactService.ensure_output_date_dir(ws)
        return ws, working_dir, str(output_dir)
    
    @staticmethod
    async def chat(
        db: Session,
        user: User,
        message: str,
        conversation_id: Optional[int] = None,
        file_ids: Optional[List[int]] = None,
        workspace_id: Optional[int] = None,
    ) -> Dict:
        """
        处理聊天请求 - ReAct Agent 模式（非流式）
        
        Returns:
            {
                "response": str,
                "conversation_id": int,
                "message_id": int,
                "tokens_used": int,
                "files_referenced": List[int],
                "steps": List[Dict],
            }
        """
        # 获取或创建对话
        if conversation_id:
            conversation = ConversationService.get_by_id(db, conversation_id)
            if not conversation or conversation.owner_id != user.id:
                raise ValueError("对话不存在或无权访问")
        else:
            title = message[:20] + "..." if len(message) > 20 else message
            conversation = ConversationService.create(
                db, user, title=title, model=llm_client.model
            )
        
        # 添加用户消息
        ConversationService.add_message(
            db, conversation.id, MessageRole.USER, message
        )
        
        # 解析文件名为 Agent 可用格式，并提取预加载内容
        file_names = ChatService._resolve_file_names(db, file_ids or [], user.id)
        file_contents = ChatService._extract_file_contents(db, file_ids or [], user.id)

        # 构建对话历史（多轮对话记忆）
        history = ChatService._build_conversation_history(db, conversation_id)

        # 解析工作空间目录
        workspace, working_dir, output_dir = ChatService._resolve_workspace_and_dirs(db, user, workspace_id)

        # 初始化 Agent
        agent = AgentService(working_dir=working_dir, output_dir=output_dir)

        saved_path = output_dir

        # 运行 Agent
        try:
            result = await agent.run(user, message,
                                     file_names=file_names,
                                     file_contents=file_contents,
                                     history=history)
        except Exception as e:
            logger.error(f"Agent run failed: {e}")
            result = {
                "success": False,
                "answer": "抱歉，AI 处理过程出现错误。请稍后重试。",
                "steps": [{"type": "error", "content": str(e)}],
                "tokens_used": 0,
            }

        # 如果 Agent 返回执行错误，给出友好兜底回复
        if not result.get("success", True):
            result["answer"] = "抱歉，AI 处理过程出现错误。请稍后重试。"

        # 答案中的 /sandbox_output 虚拟路径替换为真实输出路径
        result["answer"] = ChatService._replace_sandbox_paths(result["answer"], output_dir)

        # 保存 AI 回复
        assistant_msg = ConversationService.add_message(
            db, conversation.id, MessageRole.ASSISTANT,
            result["answer"], result.get("tokens_used", 0)
        )

        # 回答本身也作为交付物存为 Markdown（保证「结果已保存到…」始终有真实内容）
        ChatService._save_answer_markdown(output_dir, message, result["answer"])

        # 记录输出交付物
        artifacts = OutputArtifactService.scan_and_record(
            db, workspace, Path(output_dir), conversation_id=conversation.id
        )

        return {
            "response": result["answer"],
            "conversation_id": conversation.id,
            "message_id": assistant_msg.id,
            "tokens_used": result.get("tokens_used", 0),
            "files_referenced": file_ids or [],
            "steps": result.get("steps", []),
            "saved_path": str(saved_path) if saved_path else None,
            "artifacts": [
                {"filename": a.filename, "relative_path": a.relative_path, "type": a.artifact_type}
                for a in artifacts
            ],
        }
    
    @staticmethod
    async def chat_stream(
        db: Session,
        user: User,
        message: str,
        conversation_id: Optional[int] = None,
        file_ids: Optional[List[int]] = None,
        workspace_id: Optional[int] = None,
    ):
        """
        流式聊天 - ReAct Agent 模式
        
        Yields:
            str: SSE 格式的数据块
        """
        # 获取或创建对话
        if conversation_id:
            conversation = ConversationService.get_by_id(db, conversation_id)
            if not conversation or conversation.owner_id != user.id:
                raise ValueError("对话不存在或无权访问")
        else:
            title = message[:20] + "..." if len(message) > 20 else message
            conversation = ConversationService.create(
                db, user, title=title, model=llm_client.model
            )
        
        # 添加用户消息
        ConversationService.add_message(
            db, conversation.id, MessageRole.USER, message
        )
        
        # 解析文件名并提取预加载内容
        file_names = ChatService._resolve_file_names(db, file_ids or [], user.id)
        file_contents = ChatService._extract_file_contents(db, file_ids or [], user.id)

        # 构建对话历史（多轮对话记忆）
        history = ChatService._build_conversation_history(db, conversation_id)

        # 解析工作空间目录
        workspace, working_dir, output_dir = ChatService._resolve_workspace_and_dirs(db, user, workspace_id)

        # 初始化 Agent
        agent = AgentService(working_dir=working_dir, output_dir=output_dir)

        saved_path = output_dir

        # 发送 conversation_id 给前端（新对话时前端需要知道 ID）
        yield f'data: {{"type": "conversation_id", "conversation_id": {conversation.id}}}\n\n'

        # 流式运行并收集最终答案
        full_answer = ""
        try:
            buffered_events = []
            async for event in agent.run_stream(user, message,
                                                 file_names=file_names,
                                                 file_contents=file_contents,
                                                 history=history):
                if event.strip() == "data: [DONE]":
                    continue
                # 答案事件先替换虚拟路径再透传给前端
                if event.startswith("data: "):
                    try:
                        data = json.loads(event[6:])
                        if data.get("type") == "answer":
                            data["content"] = ChatService._replace_sandbox_paths(
                                data.get("content", ""), output_dir
                            )
                            full_answer = data["content"]
                            event = f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
                    except json.JSONDecodeError:
                        pass
                buffered_events.append(event)
                yield event
            
            # 答案中的 /sandbox_output 虚拟路径替换为真实输出路径
            full_answer = ChatService._replace_sandbox_paths(full_answer, output_dir)

            # 保存完整响应到数据库
            if full_answer:
                ConversationService.add_message(
                    db, conversation.id, MessageRole.ASSISTANT,
                    full_answer, tokens_used=0
                )

            # 回答本身也作为交付物存为 Markdown
            ChatService._save_answer_markdown(output_dir, message, full_answer)

            # 记录输出交付物
            OutputArtifactService.scan_and_record(
                db, workspace, Path(output_dir), conversation_id=conversation.id
            )

            # 通知前端结果已保存，最后发送 [DONE]
            yield f'data: {{"type": "metadata", "saved_path": "{saved_path}"}}\n\n'
            yield "data: [DONE]\n\n"
                
        except Exception as e:
            logger.error(f"Agent stream failed: {e}")
            # 失败也尽力保存已收集的回答内容
            try:
                ChatService._save_answer_markdown(
                    output_dir, message,
                    full_answer or f"（处理失败：{e}）",
                )
            except Exception:
                pass
            yield f'data: {{"type": "error", "content": "{str(e)}"}}\n\n'
            yield "data: [DONE]\n\n"
