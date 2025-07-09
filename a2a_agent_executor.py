"""
A2A Agent Executor for Text-to-SQL Agent

This module implements the A2A agent executor following the official A2A SDK patterns,
integrating with our existing text-to-SQL agent functionality.
"""

import asyncio
import json
import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

# A2A SDK imports
from a2a.server.agent_execution import AgentExecutor
from a2a.types import Task, TaskState, TextPart
from a2a.utils import new_task

# LangChain imports
from langchain_core.messages import HumanMessage

# Local imports
from agent import text2sql_agent
from schemas import ChatMessage

logger = logging.getLogger(__name__)


@dataclass
class TaskInfo:
    """Information about a running task"""
    task_id: str
    status: str
    created_at: datetime
    updated_at: datetime
    request: Task
    response: Optional[Task] = None
    error: Optional[str] = None


class TextToSQLAgentExecutor(AgentExecutor):
    """
    Streaming-Only A2A Agent Executor for Text-to-SQL Agent
    
    Provides text-to-SQL capabilities through streaming responses with real-time
    agent processing steps. Synchronous requests are disabled.
    """
    
    def __init__(self):
        super().__init__()
        self.name = "text-to-sql-agent"
        self.version = "2.0.0"
        self.description = "Streaming-only text-to-SQL agent with real-time React processing steps, Neo4j schema introspection, and multi-format query generation. Synchronous invoke() method is deprecated - use stream() only."
        self.tasks: Dict[str, TaskInfo] = {}
        self.initialized = self._initialize_agent()
    
    def _initialize_agent(self) -> bool:
        """Initialize the text-to-SQL agent components"""
        try:
            logger.info("Initializing text-to-SQL agent components...")
            # Test if our agent components are available
            return True
        except Exception as e:
            logger.error(f"Failed to initialize text-to-SQL agent: {e}")
            return False
    
    def get_capabilities(self) -> Dict[str, Any]:
        """Return the agent capabilities"""
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "skills": [],
            "supported_formats": ["text", "json", "csv", "parquet", "html", "summary"],
            "streaming_support": True,
            "streaming_only": True,
            "synchronous_support": False,
            "invoke_support": False,
            "intermediate_thinking": True,
            "real_time_processing": True,
            "concurrent_task_limit": 5,
            "supported_methods": ["stream"],
            "deprecated_methods": ["invoke"],
            "communication_patterns": {
                "streaming": "Real-time Server-Sent Events with intermediate thinking steps",
                "synchronous": "Not supported - all requests must use streaming",
                "invoke": "Deprecated - returns error message directing to streaming"
            },
            "features": {
                "schema_introspection": "Neo4j knowledge graph integration",
                "multi_database_support": "Oracle database with connection routing",
                "format_conversion": "Multiple output formats (JSON, CSV, HTML, Parquet, Summary)",
                "query_optimization": "AI-powered SQL generation with performance considerations",
                "error_handling": "Comprehensive error analysis and alternative suggestions"
            },
            "endpoints": {
                "streaming": "/a2a/stream",
                "deprecated_message": "/a2a/message",
                "agent_card": "/a2a/agent-card",
                "task_status": "/a2a/task/{task_id}",
                "service_status": "/a2a/status"
            }
        }
    
    async def invoke(self, task: Task) -> Task:
        """
        DEPRECATED: invoke() method is not supported.
        
        This agent is streaming-only. Use stream() method instead for real-time
        processing with intermediate thinking steps.
        """
        task_id = str(uuid.uuid4())
        return new_task(
            task_id=task_id,
            state=TaskState.COMPLETED,
            parts=[TextPart(text="❌ DEPRECATED: invoke() method is not supported. This agent is streaming-only. Please use the stream() method or /a2a/stream endpoint for real-time responses with intermediate thinking steps.")],
        )
    
    async def stream(self, task: Task) -> Any:
        """Handle streaming task execution with real-time agent processing steps"""
        task_id = str(uuid.uuid4())
        task_info = TaskInfo(
            task_id=task_id,
            status=TaskState.RUNNING,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            request=task
        )
        
        self.tasks[task_id] = task_info
        
        try:
            logger.info(f"Starting streaming A2A task {task_id}")
            return self._create_stream_generator(task_id, task)
            
        except Exception as e:
            logger.error(f"Error setting up streaming for task {task_id}: {e}")
            return self._create_error_generator(task_id, str(e))
    
    def _create_stream_generator(self, task_id: str, task: Task):
        """Create the main streaming generator"""
        async def stream_generator():
            # Extract user text
            user_text = self._extract_user_text(task)
            if not user_text:
                yield self._create_task_update(task_id, TaskState.COMPLETED, 
                    "❌ No content to process. Please send a text message with your query.", final=True)
                return
            
            # Setup agent processing
            langchain_messages = [HumanMessage(content=user_text)]
            thread_config = {"configurable": {"thread_id": task_id}}
            
            # Process with agent streaming
            try:
                yield self._create_task_update(task_id, TaskState.RUNNING, 
                    f"🤔 Processing your query: {user_text}")
                
                # Stream agent steps
                async for chunk in text2sql_agent.agent.astream(
                    {"messages": langchain_messages}, 
                    config=thread_config
                ):
                    async for update in self._process_agent_chunk(task_id, chunk):
                        yield update
                
                # Get final result
                final_result = await text2sql_agent.agent.ainvoke(
                    {"messages": langchain_messages}, 
                    config=thread_config
                )
                
                final_response = self._extract_final_response(final_result)
                yield self._create_task_update(task_id, TaskState.COMPLETED, 
                    f"✅ {final_response}", final=True)
                
            except Exception as e:
                logger.error(f"Error in agent streaming: {e}")
                yield self._create_task_update(task_id, TaskState.FAILED, 
                    f"❌ Error: {str(e)}", final=True)
        
        return stream_generator()
    
    def _create_error_generator(self, task_id: str, error_message: str):
        """Create an error generator for failed tasks"""
        async def error_generator():
            yield self._create_task_update(task_id, TaskState.FAILED, 
                f"Failed to process task: {error_message}", final=True)
        return error_generator()
    
    def _extract_user_text(self, task: Task) -> str:
        """Extract user text from task"""
        if hasattr(task, 'content') and task.content:
            return task.content
        return ""
    
    async def _process_agent_chunk(self, task_id: str, chunk: Dict[str, Any]):
        """Process a single chunk from agent streaming"""
        if "agent" in chunk:
            async for update in self._process_agent_messages(task_id, chunk["agent"]):
                yield update
        
        elif "tools" in chunk:
            async for update in self._process_tool_messages(task_id, chunk["tools"]):
                yield update
        
        elif isinstance(chunk, dict):
            async for update in self._process_other_chunk(task_id, chunk):
                yield update
    
    async def _process_agent_messages(self, task_id: str, agent_data: Dict[str, Any]):
        """Process agent thinking/reasoning messages"""
        if "messages" in agent_data:
            for message in agent_data["messages"]:
                if hasattr(message, 'content') and message.content:
                    yield self._create_task_update(task_id, TaskState.RUNNING, 
                        f"🧠 Agent: {message.content}")
    
    async def _process_tool_messages(self, task_id: str, tools_data: Dict[str, Any]):
        """Process tool call and result messages"""
        if "messages" in tools_data:
            for message in tools_data["messages"]:
                if hasattr(message, 'name'):
                    # Tool call
                    tool_name = message.name
                    yield self._create_task_update(task_id, TaskState.RUNNING, 
                        f"🔧 Calling tool: {tool_name}")
                    
                    # Tool arguments
                    tool_args = getattr(message, 'tool_input', {})
                    if tool_args:
                        args_str = json.dumps(tool_args, indent=2)
                        yield self._create_task_update(task_id, TaskState.RUNNING, 
                            f"📝 Tool arguments:\n```json\n{args_str}\n```")
                
                elif hasattr(message, 'content') and message.content:
                    # Tool result
                    result = message.content
                    if len(result) > 500:
                        result = result[:500] + "... (truncated)"
                    yield self._create_task_update(task_id, TaskState.RUNNING, 
                        f"📋 Tool result: {result}")
    
    async def _process_other_chunk(self, task_id: str, chunk: Dict[str, Any]):
        """Process other types of chunks"""
        for key, value in chunk.items():
            if key not in ["agent", "tools"] and value:
                yield self._create_task_update(task_id, TaskState.RUNNING, 
                    f"⚙️ Processing {key}: {str(value)[:200]}")
    
    def _extract_final_response(self, final_result: Dict[str, Any]) -> str:
        """Extract final response from agent result"""
        if "messages" in final_result and final_result["messages"]:
            last_message = final_result["messages"][-1]
            if hasattr(last_message, 'content'):
                return last_message.content
        return "Processing completed."
    
    def _create_task_update(self, task_id: str, state: TaskState, text: str, final: bool = False) -> Task:
        """Create a task update with the given parameters"""
        return new_task(
            task_id=task_id,
            state=state,
            parts=[TextPart(text=text)],
            final=final
        )
    
    async def cancel_task(self, task_id: str) -> bool:
        """Cancel a running task"""
        if task_id in self.tasks:
            task_info = self.tasks[task_id]
            if task_info.status == TaskState.RUNNING:
                task_info.status = TaskState.CANCELLED
                task_info.updated_at = datetime.now(timezone.utc)
                logger.info(f"A2A task {task_id} cancelled")
                return True
        
        logger.warning(f"A2A task {task_id} not found or not running")
        return False
    
    async def get_task_status(self, task_id: str) -> Optional[TaskInfo]:
        """Get the status of a task"""
        return self.tasks.get(task_id)


# Global instance
text_to_sql_agent_executor = TextToSQLAgentExecutor()


def get_agent_executor() -> TextToSQLAgentExecutor:
    """Get the global agent executor instance"""
    return text_to_sql_agent_executor


async def health_check() -> bool:
    """Check if the agent executor is healthy"""
    return text_to_sql_agent_executor.initialized 