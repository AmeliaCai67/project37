from typing import List, Dict, Optional
from pathlib import Path
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
            WorkspaceService.sync_external_to_copy(ws, copy_dir)
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

        # 保存 AI 回复
        assistant_msg = ConversationService.add_message(
            db, conversation.id, MessageRole.ASSISTANT,
            result["answer"], result.get("tokens_used", 0)
        )

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
                buffered_events.append(event)
                yield event
                # 从 SSE 事件中提取最终答案
                if event.startswith("data: "):
                    try:
                        data = json.loads(event[6:])
                        if data.get("type") == "answer":
                            full_answer = data.get("content", "")
                    except json.JSONDecodeError:
                        pass
            
            # 保存完整响应到数据库
            if full_answer:
                ConversationService.add_message(
                    db, conversation.id, MessageRole.ASSISTANT,
                    full_answer, tokens_used=0
                )

            # 记录输出交付物
            OutputArtifactService.scan_and_record(
                db, workspace, Path(output_dir), conversation_id=conversation.id
            )

            # 通知前端结果已保存，最后发送 [DONE]
            yield f'data: {{"type": "metadata", "saved_path": "{saved_path}"}}\n\n'
            yield "data: [DONE]\n\n"
                
        except Exception as e:
            logger.error(f"Agent stream failed: {e}")
            yield f'data: {{"type": "error", "content": "{str(e)}"}}\n\n'
            yield "data: [DONE]\n\n"
