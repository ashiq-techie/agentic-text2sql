"""
FastAPI application for the text-to-SQL agent with Python A2A SDK integration.

Combines our existing FastAPI endpoints with the official Python A2A SDK
for standardized agent communication.
"""
import logging
from contextlib import asynccontextmanager
from typing import List, Dict, Any
import uvicorn
from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import time
import asyncio

from config import settings
from schemas import (
    ChatRequest, ChatResponse, HealthResponse, 
    ChatMessage, AgentResponse
)
from clients import initialize_clients, shutdown_clients, health_check_all
from agent import process_chat_request, agent_health_check
from schema_introspection import schema_introspector

# Python A2A SDK imports
from python_a2a import A2AClient, Message, TextContent, MessageRole, FunctionCallContent, FunctionParameter
from a2a_agent_server import text_to_sql_agent
from a2a_agent_card_sdk import AGENT_CARD_SDK

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    logger.info("Starting text-to-SQL agent application with A2A SDK")
    
    try:
        # Initialize database clients
        await initialize_clients()
        
        # Initialize A2A agent
        await text_to_sql_agent.initialize()
        
        logger.info("Application startup complete")
        yield
        
    except Exception as e:
        logger.error(f"Startup failed: {e}")
        raise
    
    finally:
        # Cleanup
        logger.info("Shutting down application")
        await shutdown_clients()


# Create FastAPI app
app = FastAPI(
    title="Text-to-SQL Agent with A2A SDK",
    description="Advanced text-to-SQL agent using Neo4j knowledge graph, LangGraph, and Python A2A SDK",
    version="2.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", response_model=Dict[str, str])
async def root():
    """Root endpoint."""
    return {
        "message": "Text-to-SQL Agent API with A2A SDK",
        "version": "2.0.0",
        "docs": "/docs",
        "health": "/health",
        "a2a_agent_card": "/a2a/agent-card",
        "a2a_message": "/a2a/message"
    }


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    try:
        # Check database connections
        db_health = await health_check_all()
        
        # Check agent health
        agent_healthy = await agent_health_check()
        
        # Check A2A agent health
        a2a_healthy = text_to_sql_agent._initialized
        
        # Overall health status
        all_healthy = (
            all(status == "healthy" for status in db_health.values()) and
            agent_healthy and a2a_healthy
        )
        
        return HealthResponse(
            status="healthy" if all_healthy else "unhealthy",
            dependencies={
                **db_health,
                "agent": "healthy" if agent_healthy else "unhealthy",
                "a2a_agent": "healthy" if a2a_healthy else "unhealthy"
            }
        )
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return HealthResponse(
            status="error",
            dependencies={"error": str(e)}
        )


@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    """
    Original chat endpoint for direct text-to-SQL conversion.
    
    This endpoint maintains backward compatibility with existing clients.
    For A2A protocol communication, use the /a2a/message endpoint.
    """
    try:
        start_time = time.time()
        logger.info(f"Received chat request with {len(request.messages)} messages")
        
        if not request.messages:
            raise HTTPException(status_code=400, detail="No messages provided")
        
        # Process the request through the agent
        response = await process_chat_request(
            messages=request.messages,
            session_id=request.session_id
        )
        
        total_time = time.time() - start_time
        logger.info(f"Chat request processed in {total_time:.3f}s")
        
        return ChatResponse(
            response=response,
            status="success"
        )
        
    except Exception as e:
        logger.error(f"Chat endpoint error: {e}")
        return ChatResponse(
            response=AgentResponse(
                message=f"I apologize, but I encountered an error: {str(e)}",
                execution_time=0.0,
                session_id=request.session_id
            ),
            status="error",
            error=str(e)
        )


@app.post("/introspect-schema")
async def introspect_schema_endpoint(
    background_tasks: BackgroundTasks,
    schema_name: str = None
):
    """
    Endpoint to introspect Oracle database schema and store it in Neo4j.
    
    This is typically run once or periodically to update the knowledge graph.
    """
    try:
        logger.info(f"Starting schema introspection for schema: {schema_name}")
        
        # Run schema introspection in background
        background_tasks.add_task(
            _introspect_and_store_schema,
            schema_name
        )
        
        return {
            "message": "Schema introspection started",
            "schema_name": schema_name,
            "status": "in_progress"
        }
        
    except Exception as e:
        logger.error(f"Schema introspection failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


async def _introspect_and_store_schema(schema_name: str = None):
    """Background task to introspect and store schema."""
    try:
        logger.info("Starting schema introspection background task")
        
        # Introspect Oracle schema
        schema_graph = await schema_introspector.introspect_oracle_schema(schema_name)
        
        # Store in Neo4j
        await schema_introspector.store_schema_in_neo4j(schema_graph)
        
        logger.info("Schema introspection completed successfully")
        
    except Exception as e:
        logger.error(f"Schema introspection background task failed: {e}")


@app.get("/schema/search")
async def search_schema_endpoint(
    query: str,
    similarity_threshold: float = 0.6
):
    """
    Endpoint to search for relevant schema based on query terms.
    
    Useful for exploring what tables and columns are available for a given query.
    """
    try:
        logger.info(f"Searching schema for: {query}")
        
        results = await schema_introspector.find_relevant_schema(
            query, similarity_threshold
        )
        
        return {
            "query": query,
            "similarity_threshold": similarity_threshold,
            "results": results,
            "count": len(results)
        }
        
    except Exception as e:
        logger.error(f"Schema search failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/schema/context")
async def get_schema_context_endpoint(table_names: str):
    """
    Endpoint to get complete schema context for specific tables.
    
    Args:
        table_names: Comma-separated list of table names
    """
    try:
        logger.info(f"Getting schema context for tables: {table_names}")
        
        table_list = [name.strip().upper() for name in table_names.split(',')]
        
        context = await schema_introspector.get_schema_context(table_list)
        
        return {
            "table_names": table_list,
            "context": context
        }
        
    except Exception as e:
        logger.error(f"Get schema context failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/schema/inferred-relationships")
async def get_inferred_relationships_endpoint():
    """
    Endpoint to get all inferred foreign key relationships.
    
    Returns relationships that were inferred from naming conventions
    along with confidence scores and statistics.
    """
    try:
        logger.info("Getting inferred foreign key relationships")
        
        validation_results = await schema_introspector.validate_inferred_relationships()
        
        return {
            "message": "Inferred foreign key relationships retrieved successfully",
            "inference_enabled": settings.enable_fk_inference,
            "similarity_threshold": settings.fk_inference_similarity_threshold,
            **validation_results
        }
        
    except Exception as e:
        logger.error(f"Get inferred relationships failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/metrics")
async def get_metrics():
    """Endpoint to get basic application metrics."""
    try:
        # Get database health
        db_health = await health_check_all()
        
        # Get agent health
        agent_healthy = await agent_health_check()
        
        return {
            "database_health": db_health,
            "agent_health": "healthy" if agent_healthy else "unhealthy",
            "a2a_agent_health": "healthy" if text_to_sql_agent._initialized else "unhealthy",
            "uptime": "running",
            "version": "2.0.0"
        }
        
    except Exception as e:
        logger.error(f"Metrics endpoint failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ========================================
# PYTHON A2A SDK ENDPOINTS
# ========================================

@app.get("/a2a/agent-card")
async def get_a2a_agent_card():
    """
    A2A SDK: Get agent card describing capabilities.
    
    Returns the agent card using the Python A2A SDK format.
    """
    return AGENT_CARD_SDK


@app.post("/a2a/message")
async def send_a2a_message(message_data: Dict[str, Any]):
    """
    A2A SDK: Send a message to the agent using Python A2A SDK format.
    
    This endpoint accepts messages in the Python A2A SDK format and
    returns responses in the same format.
    """
    try:
        logger.info("Received A2A SDK message")
        
        # Parse the message using Python A2A SDK
        if message_data.get("content", {}).get("type") == "text":
            message = Message(
                content=TextContent(text=message_data["content"]["text"]),
                role=MessageRole.USER,
                message_id=message_data.get("message_id"),
                conversation_id=message_data.get("conversation_id")
            )
        elif message_data.get("content", {}).get("type") == "function_call":
            # Handle function calls
            function_data = message_data["content"]
            parameters = [
                FunctionParameter(name=k, value=v) 
                for k, v in function_data.get("parameters", {}).items()
            ]
            
            message = Message(
                content=FunctionCallContent(
                    name=function_data["name"],
                    parameters=parameters
                ),
                role=MessageRole.USER,
                message_id=message_data.get("message_id"),
                conversation_id=message_data.get("conversation_id")
            )
        else:
            raise HTTPException(status_code=400, detail="Unsupported message content type")
        
        # Process the message through our A2A agent
        response = text_to_sql_agent.handle_message(message)
        
        # Return the response in A2A SDK format
        return {
            "message_id": response.message_id,
            "conversation_id": response.conversation_id,
            "parent_message_id": response.parent_message_id,
            "role": response.role.value,
            "content": response.content.__dict__,
            "timestamp": response.timestamp.isoformat() if response.timestamp else None
        }
        
    except Exception as e:
        logger.error(f"A2A SDK message failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/a2a/function-call")
async def call_a2a_function(function_data: Dict[str, Any]):
    """
    A2A SDK: Call a specific function on the agent.
    
    This is a convenience endpoint for making function calls directly.
    """
    try:
        function_name = function_data.get("function_name")
        parameters = function_data.get("parameters", {})
        
        logger.info(f"Received A2A function call: {function_name}")
        
        # Create function call message
        param_objects = [
            FunctionParameter(name=k, value=v) 
            for k, v in parameters.items()
        ]
        
        message = Message(
            content=FunctionCallContent(
                name=function_name,
                parameters=param_objects
            ),
            role=MessageRole.USER
        )
        
        # Process through A2A agent
        response = text_to_sql_agent.handle_message(message)
        
        # Return just the function response data
        if hasattr(response.content, 'response'):
            return response.content.response
        else:
            return {"text": response.content.text}
        
    except Exception as e:
        logger.error(f"A2A function call failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    # Run the application
    uvicorn.run(
        "main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.debug,
        log_level="info"
    ) 