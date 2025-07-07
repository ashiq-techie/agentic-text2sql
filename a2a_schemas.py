"""
A2A (Agent2Agent) Protocol Schemas

Based on the official A2A specification:
https://github.com/a2aproject/A2A/blob/main/specification/json/a2a.json
"""
from typing import Dict, Any, List, Optional, Union, Literal
from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum
import uuid


class TaskStatus(str, Enum):
    """Task status enumeration."""
    CREATED = "created"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed" 
    FAILED = "failed"
    CANCELLED = "cancelled"
    INPUT_REQUIRED = "input_required"


class PartType(str, Enum):
    """Part type enumeration."""
    TEXT = "text"
    FILE = "file"
    DATA = "data"
    IMAGE = "image"
    AUDIO = "audio"
    VIDEO = "video"


class MessageRole(str, Enum):
    """Message role enumeration."""
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


# Part Types
class BasePart(BaseModel):
    """Base part model."""
    type: PartType
    

class TextPart(BasePart):
    """Text content part."""
    type: Literal[PartType.TEXT] = PartType.TEXT
    text: str = Field(..., description="The text content")


class FilePart(BasePart):
    """File content part."""
    type: Literal[PartType.FILE] = PartType.FILE
    file_name: str = Field(..., description="Name of the file")
    mime_type: str = Field(..., description="MIME type of the file")
    file_data: str = Field(..., description="Base64 encoded file data")


class DataPart(BasePart):
    """Structured data part."""
    type: Literal[PartType.DATA] = PartType.DATA
    data: Dict[str, Any] = Field(..., description="Structured data object")
    schema_name: Optional[str] = Field(None, description="Schema identifier for the data")


class ImagePart(BasePart):
    """Image content part."""
    type: Literal[PartType.IMAGE] = PartType.IMAGE
    image_data: str = Field(..., description="Base64 encoded image data")
    mime_type: str = Field(default="image/png", description="MIME type of the image")
    width: Optional[int] = Field(None, description="Image width in pixels")
    height: Optional[int] = Field(None, description="Image height in pixels")


# Union type for all part types
Part = Union[TextPart, FilePart, DataPart, ImagePart]


class Artefact(BaseModel):
    """Artefact containing parts and metadata."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Unique artefact identifier")
    title: Optional[str] = Field(None, description="Human-readable title")
    description: Optional[str] = Field(None, description="Description of the artefact")
    parts: List[Part] = Field(..., description="List of parts in this artefact")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional metadata")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Creation timestamp")


class Message(BaseModel):
    """A2A Message model."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Unique message identifier")
    role: MessageRole = Field(..., description="Role of the message sender")
    parts: List[Part] = Field(..., description="List of parts in this message")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Message timestamp")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional message metadata")


class TaskInput(BaseModel):
    """Task input specification."""
    messages: List[Message] = Field(..., description="Input messages for the task")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional input metadata")


class TaskOutput(BaseModel):
    """Task output specification."""
    messages: List[Message] = Field(default_factory=list, description="Output messages from the task")
    artefacts: List[Artefact] = Field(default_factory=list, description="Output artefacts from the task")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional output metadata")


class TaskState(BaseModel):
    """Task state information."""
    status: TaskStatus = Field(..., description="Current task status")
    progress: Optional[float] = Field(None, ge=0.0, le=1.0, description="Task progress (0.0 to 1.0)")
    status_message: Optional[str] = Field(None, description="Human-readable status description")
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="Last update timestamp")


class Task(BaseModel):
    """A2A Task model."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Unique task identifier")
    input: TaskInput = Field(..., description="Task input")
    output: Optional[TaskOutput] = Field(None, description="Task output (when completed)")
    state: TaskState = Field(..., description="Current task state")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Task creation timestamp")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional task metadata")


class Capability(BaseModel):
    """Agent capability description."""
    name: str = Field(..., description="Capability name")
    description: str = Field(..., description="Capability description")
    input_types: List[str] = Field(..., description="Supported input types")
    output_types: List[str] = Field(..., description="Supported output types")
    parameters: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Capability parameters")


class AgentCard(BaseModel):
    """A2A Agent Card describing agent capabilities."""
    id: str = Field(..., description="Unique agent identifier")
    name: str = Field(..., description="Agent name")
    description: str = Field(..., description="Agent description")
    version: str = Field(default="1.0.0", description="Agent version")
    capabilities: List[Capability] = Field(..., description="List of agent capabilities")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional agent metadata")
    
    # A2A Protocol specific fields
    streaming: bool = Field(default=False, description="Whether agent supports streaming")
    max_concurrent_tasks: int = Field(default=1, description="Maximum concurrent tasks")
    supported_formats: List[str] = Field(default_factory=list, description="Supported content formats")
    

# Request/Response Models
class TaskSendRequest(BaseModel):
    """Request model for sending a task."""
    input: TaskInput = Field(..., description="Task input")
    accepted_output_modes: Optional[List[str]] = Field(None, description="Accepted output formats")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Request metadata")


class TaskSendResponse(BaseModel):
    """Response model for task send."""
    task_id: str = Field(..., description="Created task identifier")
    status: TaskStatus = Field(..., description="Initial task status")


class TaskGetResponse(BaseModel):
    """Response model for task get."""
    task: Task = Field(..., description="Complete task information")


class TaskSubscribeRequest(BaseModel):
    """Request model for task subscription."""
    input: TaskInput = Field(..., description="Task input")
    accepted_output_modes: Optional[List[str]] = Field(None, description="Accepted output formats")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Request metadata")


# Streaming Event Models
class StreamEvent(BaseModel):
    """Base streaming event."""
    event: str = Field(..., description="Event type")
    data: Dict[str, Any] = Field(..., description="Event data")


class TaskProgressEvent(StreamEvent):
    """Task progress streaming event."""
    event: Literal["task_progress"] = "task_progress"
    data: Dict[str, Any] = Field(..., description="Progress data including task_id, progress, status")


class TaskCompleteEvent(StreamEvent):
    """Task completion streaming event."""
    event: Literal["task_complete"] = "task_complete"
    data: Dict[str, Any] = Field(..., description="Completion data including task_id and output")


class TaskErrorEvent(StreamEvent):
    """Task error streaming event."""
    event: Literal["task_error"] = "task_error"
    data: Dict[str, Any] = Field(..., description="Error data including task_id and error details")


# Utility functions for creating common parts
def create_text_part(text: str) -> TextPart:
    """Create a text part."""
    return TextPart(text=text)


def create_data_part(data: Dict[str, Any], schema_name: Optional[str] = None) -> DataPart:
    """Create a data part."""
    return DataPart(data=data, schema_name=schema_name)


def create_file_part(file_name: str, file_data: str, mime_type: str) -> FilePart:
    """Create a file part."""
    return FilePart(file_name=file_name, file_data=file_data, mime_type=mime_type)


def create_user_message(content: str) -> Message:
    """Create a user message with text content."""
    return Message(
        role=MessageRole.USER,
        parts=[create_text_part(content)]
    )


def create_assistant_message(content: str, data: Optional[Dict[str, Any]] = None) -> Message:
    """Create an assistant message with optional structured data."""
    parts = [create_text_part(content)]
    if data:
        parts.append(create_data_part(data))
    
    return Message(
        role=MessageRole.ASSISTANT,
        parts=parts
    ) 