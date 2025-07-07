"""
A2A Task Manager for Text-to-SQL Agent

Manages the lifecycle of A2A tasks and integrates with our existing
text-to-SQL agent system.
"""
import asyncio
import logging
from typing import Dict, Optional, List, Any, Callable, AsyncGenerator
from datetime import datetime
import json
import traceback

from a2a_schemas import (
    Task, TaskStatus, TaskState, TaskInput, TaskOutput, 
    Message, MessageRole, TextPart, DataPart, Artefact,
    create_user_message, create_assistant_message, create_text_part, create_data_part
)
from agent import create_text_to_sql_agent, invoke_agent, create_agent_session


logger = logging.getLogger(__name__)


class A2ATaskManager:
    """
    Manages A2A tasks for the text-to-SQL agent.
    
    This class handles task lifecycle, integrates with our existing agent system,
    and provides both synchronous and streaming interfaces.
    """
    
    def __init__(self):
        self.tasks: Dict[str, Task] = {}
        self.task_callbacks: Dict[str, List[Callable]] = {}
        self._agent = None
        self._agent_session = None
        
    async def initialize(self):
        """Initialize the task manager and agent."""
        try:
            self._agent = await create_text_to_sql_agent()
            self._agent_session = await create_agent_session()
            logger.info("A2A Task Manager initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize A2A Task Manager: {e}")
            raise
    
    async def create_task(self, task_input: TaskInput, metadata: Optional[Dict[str, Any]] = None) -> Task:
        """
        Create a new A2A task.
        
        Args:
            task_input: The input for the task
            metadata: Optional metadata for the task
            
        Returns:
            Created task instance
        """
        task = Task(
            input=task_input,
            state=TaskState(
                status=TaskStatus.CREATED,
                status_message="Task created and queued for processing"
            ),
            metadata=metadata or {}
        )
        
        self.tasks[task.id] = task
        logger.info(f"Created task {task.id}")
        return task
    
    async def execute_task(self, task_id: str) -> Task:
        """
        Execute a task synchronously.
        
        Args:
            task_id: The ID of the task to execute
            
        Returns:
            The completed task
        """
        task = self.tasks.get(task_id)
        if not task:
            raise ValueError(f"Task {task_id} not found")
        
        # Update task status
        task.state.status = TaskStatus.IN_PROGRESS
        task.state.status_message = "Processing natural language query..."
        task.state.updated_at = datetime.utcnow()
        
        try:
            # Extract the user's query from the input messages
            user_query = self._extract_user_query(task.input.messages)
            
            # Convert to our agent's message format
            agent_messages = self._convert_to_agent_messages(task.input.messages)
            
            # Execute the agent
            result = await invoke_agent(
                self._agent,
                {"messages": agent_messages},
                session=self._agent_session
            )
            
            # Create output messages and artefacts
            output_messages, artefacts = self._create_output(result, user_query)
            
            # Update task with results
            task.output = TaskOutput(
                messages=output_messages,
                artefacts=artefacts,
                metadata={"execution_time": datetime.utcnow().isoformat()}
            )
            task.state.status = TaskStatus.COMPLETED
            task.state.status_message = "Task completed successfully"
            task.state.progress = 1.0
            task.state.updated_at = datetime.utcnow()
            
            logger.info(f"Task {task_id} completed successfully")
            
        except Exception as e:
            logger.error(f"Task {task_id} failed: {e}")
            task.state.status = TaskStatus.FAILED
            task.state.status_message = f"Task failed: {str(e)}"
            task.state.updated_at = datetime.utcnow()
            
            # Create error output
            error_message = create_assistant_message(
                f"I apologize, but I encountered an error processing your request: {str(e)}"
            )
            task.output = TaskOutput(
                messages=[error_message],
                metadata={"error": str(e), "traceback": traceback.format_exc()}
            )
        
        return task
    
    async def execute_task_streaming(self, task_id: str) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Execute a task with streaming updates.
        
        Args:
            task_id: The ID of the task to execute
            
        Yields:
            Task progress events
        """
        task = self.tasks.get(task_id)
        if not task:
            raise ValueError(f"Task {task_id} not found")
        
        # Update task status
        task.state.status = TaskStatus.IN_PROGRESS
        task.state.status_message = "Starting task execution..."
        task.state.updated_at = datetime.utcnow()
        
        # Send initial progress event
        yield {
            "event": "task_progress",
            "data": {
                "task_id": task_id,
                "status": task.state.status.value,
                "progress": 0.0,
                "status_message": task.state.status_message
            }
        }
        
        try:
            # Extract the user's query
            user_query = self._extract_user_query(task.input.messages)
            
            # Progress: Understanding query
            task.state.progress = 0.1
            task.state.status_message = "Understanding your query..."
            task.state.updated_at = datetime.utcnow()
            
            yield {
                "event": "task_progress",
                "data": {
                    "task_id": task_id,
                    "status": task.state.status.value,
                    "progress": task.state.progress,
                    "status_message": task.state.status_message
                }
            }
            
            # Progress: Searching schema
            task.state.progress = 0.3
            task.state.status_message = "Searching database schema..."
            task.state.updated_at = datetime.utcnow()
            
            yield {
                "event": "task_progress",
                "data": {
                    "task_id": task_id,
                    "status": task.state.status.value,
                    "progress": task.state.progress,
                    "status_message": task.state.status_message
                }
            }
            
            # Progress: Generating SQL
            task.state.progress = 0.6
            task.state.status_message = "Generating SQL query..."
            task.state.updated_at = datetime.utcnow()
            
            yield {
                "event": "task_progress",
                "data": {
                    "task_id": task_id,
                    "status": task.state.status.value,
                    "progress": task.state.progress,
                    "status_message": task.state.status_message
                }
            }
            
            # Convert to agent messages and execute
            agent_messages = self._convert_to_agent_messages(task.input.messages)
            result = await invoke_agent(
                self._agent,
                {"messages": agent_messages},
                session=self._agent_session
            )
            
            # Progress: Executing query
            task.state.progress = 0.8
            task.state.status_message = "Executing query..."
            task.state.updated_at = datetime.utcnow()
            
            yield {
                "event": "task_progress",
                "data": {
                    "task_id": task_id,
                    "status": task.state.status.value,
                    "progress": task.state.progress,
                    "status_message": task.state.status_message
                }
            }
            
            # Create output
            output_messages, artefacts = self._create_output(result, user_query)
            
            # Complete the task
            task.output = TaskOutput(
                messages=output_messages,
                artefacts=artefacts,
                metadata={"execution_time": datetime.utcnow().isoformat()}
            )
            task.state.status = TaskStatus.COMPLETED
            task.state.status_message = "Task completed successfully"
            task.state.progress = 1.0
            task.state.updated_at = datetime.utcnow()
            
            # Send completion event
            yield {
                "event": "task_complete",
                "data": {
                    "task_id": task_id,
                    "status": task.state.status.value,
                    "output": task.output.dict()
                }
            }
            
            logger.info(f"Task {task_id} completed successfully with streaming")
            
        except Exception as e:
            logger.error(f"Task {task_id} failed during streaming: {e}")
            
            task.state.status = TaskStatus.FAILED
            task.state.status_message = f"Task failed: {str(e)}"
            task.state.updated_at = datetime.utcnow()
            
            # Create error output
            error_message = create_assistant_message(
                f"I apologize, but I encountered an error processing your request: {str(e)}"
            )
            task.output = TaskOutput(
                messages=[error_message],
                metadata={"error": str(e), "traceback": traceback.format_exc()}
            )
            
            # Send error event
            yield {
                "event": "task_error",
                "data": {
                    "task_id": task_id,
                    "status": task.state.status.value,
                    "error": str(e),
                    "error_details": traceback.format_exc()
                }
            }
    
    def get_task(self, task_id: str) -> Optional[Task]:
        """Get a task by ID."""
        return self.tasks.get(task_id)
    
    def _extract_user_query(self, messages: List[Message]) -> str:
        """Extract the user's query from A2A messages."""
        for message in messages:
            if message.role == MessageRole.USER:
                for part in message.parts:
                    if hasattr(part, 'text'):
                        return part.text
        return ""
    
    def _convert_to_agent_messages(self, a2a_messages: List[Message]) -> List[tuple]:
        """Convert A2A messages to our agent's message format."""
        agent_messages = []
        
        for msg in a2a_messages:
            role = msg.role.value
            
            # Combine all text parts
            text_content = ""
            for part in msg.parts:
                if hasattr(part, 'text'):
                    text_content += part.text + " "
            
            if text_content.strip():
                agent_messages.append((role, text_content.strip()))
        
        return agent_messages
    
    def _create_output(self, agent_result: Dict[str, Any], user_query: str) -> tuple[List[Message], List[Artefact]]:
        """Create A2A output messages and artefacts from agent results."""
        messages = []
        artefacts = []
        
        # Get the agent's response
        agent_response = agent_result.get("messages", [])
        
        if agent_response:
            # Get the last message (agent's response)
            last_message = agent_response[-1]
            response_text = last_message[1] if len(last_message) > 1 else ""
            
            # Create assistant message
            assistant_message = create_assistant_message(response_text)
            messages.append(assistant_message)
            
            # Check if there's structured data to include
            if "sql_query" in agent_result:
                sql_data = {
                    "query": agent_result["sql_query"],
                    "type": "sql",
                    "database": agent_result.get("database_type", "unknown")
                }
                
                # Add data part to the message
                data_part = create_data_part(sql_data, schema_name="sql_query")
                assistant_message.parts.append(data_part)
                
                # Create artefact for the SQL query
                sql_artefact = Artefact(
                    title="Generated SQL Query",
                    description=f"SQL query generated for: {user_query}",
                    parts=[
                        create_text_part(agent_result["sql_query"]),
                        create_data_part(sql_data, schema_name="sql_query")
                    ],
                    metadata={
                        "query_type": "sql",
                        "database": agent_result.get("database_type", "unknown"),
                        "generated_at": datetime.utcnow().isoformat()
                    }
                )
                artefacts.append(sql_artefact)
            
            # Check if there are query results
            if "results" in agent_result:
                results_data = {
                    "results": agent_result["results"],
                    "type": "query_results",
                    "row_count": len(agent_result["results"]) if isinstance(agent_result["results"], list) else 0
                }
                
                # Create artefact for query results
                results_artefact = Artefact(
                    title="Query Results",
                    description=f"Results from executing: {user_query}",
                    parts=[
                        create_data_part(results_data, schema_name="query_results")
                    ],
                    metadata={
                        "result_type": "query_results",
                        "row_count": results_data["row_count"],
                        "executed_at": datetime.utcnow().isoformat()
                    }
                )
                artefacts.append(results_artefact)
        
        return messages, artefacts


# Global task manager instance
task_manager = A2ATaskManager() 