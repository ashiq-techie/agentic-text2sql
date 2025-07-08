"""
A2A Agent Executor for Text-to-SQL Agent

This module implements the A2A agent executor following the official A2A SDK patterns,
integrating with our existing text-to-SQL agent functionality.

Based on the official A2A SDK example:
https://github.com/a2aproject/a2a-samples/blob/main/samples/python/agents/langgraph/app/agent_executor.py
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional, Union
from dataclasses import dataclass
import json
import uuid
from datetime import datetime

# A2A SDK imports - Required for A2A functionality
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.tasks import TaskUpdater
from a2a.types import (
    InternalError,
    InvalidParamsError,
    Part,
    Task,
    TaskState,
    TextPart,
    UnsupportedOperationError,
)
from a2a.utils import (
    new_agent_text_message,
    new_task,
)
from a2a.utils.errors import ServerError

# Import our existing text-to-SQL components
from agent import process_chat_request
from agent_tools import (
    schema_search_tool,
    get_schema_context_tool,
    neo4j_query_tool,
    oracle_query_tool
)
from schemas import ChatMessage, AgentResponse

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
    A2A Agent Executor for Text-to-SQL Agent
    
    This class implements the A2A AgentExecutor interface to provide
    text-to-SQL capabilities through the A2A protocol.
    """
    
    def __init__(self):
        super().__init__()
        self.name = "text-to-sql-agent"
        self.version = "1.0.0"
        self.description = "Text-to-SQL agent with schema introspection and query generation"
        self.tasks: Dict[str, TaskInfo] = {}
        self.initialized = False
        
        # Initialize the agent
        self._initialize_agent()
    
    def _initialize_agent(self):
        """Initialize the text-to-SQL agent components"""
        try:
            # Test if our agent components are available
            logger.info("Initializing text-to-SQL agent components...")
            self.initialized = True
            logger.info("Text-to-SQL agent initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize text-to-SQL agent: {e}")
            self.initialized = False
    
    def get_capabilities(self) -> Dict[str, Any]:
        """
        Return the agent capabilities
        
        Following the A2A SDK pattern for agent capabilities
        """
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "skills": [
                {
                    "name": "generate_sql",
                    "description": "Generate SQL queries from natural language",
                    "parameters": [
                        {
                            "name": "query",
                            "type": "string",
                            "description": "Natural language query to convert to SQL",
                            "required": True
                        },
                        {
                            "name": "database_name",
                            "type": "string",
                            "description": "Target database name (optional)",
                            "required": False
                        }
                    ]
                },
                {
                    "name": "search_schema",
                    "description": "Search database schema for relevant tables and columns",
                    "parameters": [
                        {
                            "name": "query",
                            "type": "string",
                            "description": "Search query for schema elements",
                            "required": True
                        },
                        {
                            "name": "similarity_threshold",
                            "type": "number",
                            "description": "Similarity threshold for fuzzy matching (0.0-1.0)",
                            "required": False
                        }
                    ]
                },
                {
                    "name": "explain_query",
                    "description": "Explain what a SQL query does in natural language",
                    "parameters": [
                        {
                            "name": "sql_query",
                            "type": "string",
                            "description": "SQL query to explain",
                            "required": True
                        }
                    ]
                }
            ],
            "supported_formats": ["text", "function_call"],
            "streaming_support": True,
            "concurrent_task_limit": 5
        }
    
    async def invoke(self, task: Task) -> Task:
        """
        Handle synchronous task invocation
        
        This is the main entry point for processing A2A messages
        """
        task_id = str(uuid.uuid4())
        task_info = TaskInfo(
            task_id=task_id,
            status=TaskState.PENDING,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            request=task
        )
        
        self.tasks[task_id] = task_info
        
        try:
            logger.info(f"Processing A2A task {task_id}: {task.content if hasattr(task, 'content') else 'No content'}")
            
            # Update task status
            task_info.status = TaskState.RUNNING
            task_info.updated_at = datetime.utcnow()
            
            # Process the message
            response_parts = await self._process_task(task)
            
            # Create response
            response = new_task(
                task_id=task_id,
                state=TaskState.COMPLETED,
                parts=response_parts
            )
            
            # Update task info
            task_info.status = TaskState.COMPLETED
            task_info.response = response
            task_info.updated_at = datetime.utcnow()
            
            logger.info(f"A2A task {task_id} completed successfully")
            return response
            
        except Exception as e:
            logger.error(f"A2A task {task_id} failed: {e}")
            
            # Update task with error
            task_info.status = TaskState.FAILED
            task_info.error = str(e)
            task_info.updated_at = datetime.utcnow()
            
            # Return error response
            return new_task(
                task_id=task_id,
                state=TaskState.FAILED,
                parts=[TextPart(text=f"Error processing request: {str(e)}")],
                error=str(e)
            )
    
    async def stream(self, task: Task) -> Any:
        """
        Handle streaming task execution
        
        This allows for real-time streaming of responses
        """
        task_id = str(uuid.uuid4())
        task_info = TaskInfo(
            task_id=task_id,
            status=TaskState.RUNNING,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            request=task
        )
        
        self.tasks[task_id] = task_info
        
        try:
            logger.info(f"Starting streaming A2A task {task_id}")
            
            # For streaming, we can break down the response into chunks
            async def stream_generator():
                # Start with a partial response
                yield new_task(
                    task_id=task_id,
                    state=TaskState.RUNNING,
                    parts=[TextPart(text="Processing your request...")],
                    final=False
                )
                
                # Process the actual request
                response_parts = await self._process_task(task)
                
                # Send the final response
                yield new_task(
                    task_id=task_id,
                    state=TaskState.COMPLETED,
                    parts=response_parts,
                    final=True
                )
                
                # Update task status
                task_info.status = TaskState.COMPLETED
                task_info.updated_at = datetime.utcnow()
            
            return stream_generator()
            
        except Exception as e:
            logger.error(f"Streaming A2A task {task_id} failed: {e}")
            
            # Update task with error
            task_info.status = TaskState.FAILED
            task_info.error = str(e)
            task_info.updated_at = datetime.utcnow()
            
            # Return error in streaming format
            async def error_generator():
                yield new_task(
                    task_id=task_id,
                    state=TaskState.FAILED,
                    parts=[TextPart(text=f"Error: {str(e)}")],
                    final=True,
                    error=str(e)
                )
            
            return error_generator()
    
    async def cancel_task(self, task_id: str) -> bool:
        """
        Cancel a running task
        """
        if task_id in self.tasks:
            task_info = self.tasks[task_id]
            if task_info.status == TaskState.RUNNING:
                task_info.status = TaskState.CANCELLED
                task_info.updated_at = datetime.utcnow()
                logger.info(f"A2A task {task_id} cancelled")
                return True
        
        logger.warning(f"A2A task {task_id} not found or not running")
        return False
    
    async def get_task_status(self, task_id: str) -> Optional[TaskInfo]:
        """
        Get the status of a task
        """
        return self.tasks.get(task_id)
    
    async def _process_task(self, task: Task) -> List[Part]:
        """
        Process a task and return response parts
        
        This method handles both text and function call tasks
        """
        if not self.initialized:
            return [TextPart(text="Agent is not properly initialized")]
        
        response_parts = []
        
        # Handle text content
        if hasattr(task, 'content') and task.content:
            response_part = await self._handle_text_message(task.content)
            response_parts.append(response_part)
        
        # Handle function calls if present
        if hasattr(task, 'function_calls') and task.function_calls:
            for func_call in task.function_calls:
                response_part = await self._handle_function_call(func_call.name, func_call.parameters)
                response_parts.append(response_part)
        
        # If no content or function calls, return a default response
        if not response_parts:
            response_parts.append(TextPart(text="No content to process"))
        
        return response_parts
    
    async def _handle_text_message(self, text: str) -> Part:
        """
        Handle text messages by invoking the LangGraph agent
        """
        try:
            # Convert to our internal format
            messages = [ChatMessage(role="user", content=text)]
            
            # Invoke the agent
            agent_response = await process_chat_request(messages)
            
            # Return the response
            return TextPart(text=agent_response.message)
            
        except Exception as e:
            logger.error(f"Error handling text message: {e}")
            return TextPart(text=f"Error processing text message: {str(e)}")
    
    async def _handle_function_call(self, function_name: str, parameters: Dict[str, Any]) -> Part:
        """
        Handle function calls by routing to appropriate tools
        """
        try:
            if function_name == "generate_sql":
                # Generate SQL query
                query = parameters.get("query", "")
                database_name = parameters.get("database_name")
                
                messages = [ChatMessage(role="user", content=query)]
                agent_response = await process_chat_request(messages)
                
                result = {
                    "sql_query": agent_response.sql_query,
                    "explanation": agent_response.message,
                    "execution_time": agent_response.execution_time
                }
                
                return TextPart(text=json.dumps(result, indent=2))
            
            elif function_name == "search_schema":
                # Search schema
                query = parameters.get("query", "")
                similarity_threshold = parameters.get("similarity_threshold", 0.6)
                
                # Use the search schema tool
                search_result = await schema_search_tool.ainvoke({
                    "search_terms": query,
                    "similarity_threshold": similarity_threshold
                })
                
                return TextPart(text=search_result)
            
            elif function_name == "explain_query":
                # Explain SQL query
                sql_query = parameters.get("sql_query", "")
                
                # Use the agent to explain the query
                explanation_prompt = f"Explain what this SQL query does in natural language: {sql_query}"
                messages = [ChatMessage(role="user", content=explanation_prompt)]
                agent_response = await process_chat_request(messages)
                
                result = {
                    "explanation": agent_response.message,
                    "query": sql_query
                }
                
                return TextPart(text=json.dumps(result, indent=2))
            
            else:
                return TextPart(
                    text=json.dumps({"error": f"Unknown function: {function_name}"}, indent=2)
                )
                
        except Exception as e:
            logger.error(f"Error handling function call {function_name}: {e}")
            return TextPart(
                text=json.dumps({"error": f"Error executing function: {str(e)}"}, indent=2)
            )


# Global instance
text_to_sql_agent_executor = TextToSQLAgentExecutor()


def get_agent_executor() -> TextToSQLAgentExecutor:
    """
    Get the global agent executor instance
    """
    return text_to_sql_agent_executor


# Health check function
async def health_check() -> bool:
    """
    Check if the agent executor is healthy
    """
    return text_to_sql_agent_executor.initialized 