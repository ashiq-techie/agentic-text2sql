"""
Pydantic schemas for the text-to-SQL agent API.
"""
from typing import List, Optional, Dict, Any, Union
from pydantic import BaseModel, Field
from enum import Enum


class MessageRole(str, Enum):
    """Message roles in the chat."""
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class ChatMessage(BaseModel):
    """A single chat message."""
    role: MessageRole = Field(..., description="The role of the message sender")
    content: str = Field(..., description="The content of the message")
    timestamp: Optional[str] = Field(None, description="ISO timestamp of the message")


class ChatRequest(BaseModel):
    """Request schema for chat endpoint."""
    messages: List[ChatMessage] = Field(..., description="List of chat messages")
    session_id: Optional[str] = Field(None, description="Session identifier for context")
    max_tokens: Optional[int] = Field(None, description="Maximum tokens for response")
    temperature: Optional[float] = Field(0.1, ge=0.0, le=2.0, description="Temperature for response generation")


class QueryResult(BaseModel):
    """Result of a database query."""
    query: str = Field(..., description="The executed SQL query")
    results: List[Dict[str, Any]] = Field(..., description="Query results as list of dictionaries")
    execution_time: float = Field(..., description="Query execution time in seconds")
    row_count: int = Field(..., description="Number of rows returned")


class SchemaNode(BaseModel):
    """A node in the schema graph."""
    id: str = Field(..., description="Unique identifier for the node")
    type: str = Field(..., description="Type of node (database, table, column)")
    name: str = Field(..., description="Name of the schema object")
    properties: Dict[str, Any] = Field(default_factory=dict, description="Additional properties")


class SchemaRelationship(BaseModel):
    """A relationship in the schema graph."""
    source_id: str = Field(..., description="Source node ID")
    target_id: str = Field(..., description="Target node ID")
    type: str = Field(..., description="Type of relationship (HAS_TABLE, HAS_COLUMN, HAS_FOREIGN_KEY)")
    properties: Dict[str, Any] = Field(default_factory=dict, description="Additional properties")


class SchemaGraph(BaseModel):
    """Complete schema graph representation."""
    nodes: List[SchemaNode] = Field(..., description="List of all nodes in the schema")
    relationships: List[SchemaRelationship] = Field(..., description="List of all relationships")


class AgentResponse(BaseModel):
    """Response from the agent."""
    message: str = Field(..., description="The agent's response message")
    query_results: Optional[QueryResult] = Field(None, description="SQL query results if applicable")
    schema_used: Optional[List[str]] = Field(None, description="List of tables/columns used in the query")
    execution_time: float = Field(..., description="Total execution time in seconds")
    session_id: Optional[str] = Field(None, description="Session identifier")


class ChatResponse(BaseModel):
    """Response schema for chat endpoint."""
    response: AgentResponse = Field(..., description="The agent's response")
    status: str = Field(default="success", description="Response status")
    error: Optional[str] = Field(None, description="Error message if any")


class HealthResponse(BaseModel):
    """Health check response."""
    status: str = Field(default="healthy", description="Service health status")
    version: str = Field(default="1.0.0", description="API version")
    dependencies: Dict[str, str] = Field(default_factory=dict, description="Dependency status")


class Neo4jQueryRequest(BaseModel):
    """Request for Neo4j query execution."""
    query: str = Field(..., description="Cypher query to execute")
    parameters: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Query parameters")


class OracleQueryRequest(BaseModel):
    """Request for Oracle query execution."""
    query: str = Field(..., description="SQL query to execute")
    parameters: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Query parameters")
    fetch_size: Optional[int] = Field(100, description="Number of rows to fetch at once") 