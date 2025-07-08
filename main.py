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

# A2A SDK imports
from a2a_agent_executor import get_agent_executor, health_check as a2a_health_check

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for FastAPI application startup and shutdown."""
    # Startup
    logger.info("Starting up the application...")
    try:
        await initialize_clients()
        logger.info("Database clients initialized successfully")
        
        # Initialize A2A service
        executor = get_agent_executor()
        if executor:
            # Don't start the A2A server here as it runs on a different port
            # Just ensure the service is ready
            logger.info("A2A service initialized and ready")
        else:
            logger.warning("A2A service not available")
        
        yield
        
    except Exception as e:
        logger.error(f"Failed to start application: {e}")
        raise
    finally:
        # Shutdown
        logger.info("Shutting down the application...")
        await shutdown_clients()
        logger.info("Application shutdown complete")


# Create FastAPI app
app = FastAPI(
    title="Text-to-SQL Agent with A2A SDK",
    description="Unified text-to-SQL agent with Neo4j knowledge graph, multi-database support, Oracle thick client with Kerberos, and integrated A2A protocol",
    version="2.1.0",
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
        "message": "Unified Text-to-SQL Agent API with integrated A2A SDK",
        "version": "2.1.0",
        "docs": "/docs",
        "health": "/health",
        "a2a_agent_card": "/a2a/agent-card",
        "a2a_message": "/a2a/message",
        "a2a_stream": "/a2a/stream",
        "a2a_task_status": "/a2a/task/{task_id}",
        "a2a_service_status": "/a2a/status"
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
        a2a_healthy = await a2a_health_check()
        
        # Overall health status
        all_healthy = (
            all(status == "healthy" for status in db_health.values()) and
            agent_healthy and
            a2a_healthy
        )
        
        health_deps = {
            **db_health,
            "agent": "healthy" if agent_healthy else "unhealthy",
            "a2a_agent": "healthy" if a2a_healthy else "unhealthy"
        }
        
        return HealthResponse(
            status="healthy" if all_healthy else "unhealthy",
            dependencies=health_deps
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
    schema_name: str = None,
    database_name: str = None
):
    """
    Endpoint to introspect Oracle database schema and store it in Neo4j.
    
    This is typically run once or periodically to update the knowledge graph.
    Now supports multiple databases by specifying database_name parameter.
    """
    try:
        if database_name is None:
            database_name = settings.default_database_name
            
        logger.info(f"Starting schema introspection for database: {database_name}, schema: {schema_name}")
        
        # Run schema introspection in background
        background_tasks.add_task(
            _introspect_and_store_schema,
            schema_name,
            database_name
        )
        
        return {
            "message": "Schema introspection started",
            "database_name": database_name,
            "schema_name": schema_name,
            "status": "in_progress"
        }
        
    except Exception as e:
        logger.error(f"Schema introspection failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


async def _introspect_and_store_schema(schema_name: str = None, database_name: str = None):
    """Background task to introspect and store schema."""
    try:
        if database_name is None:
            database_name = settings.default_database_name
            
        logger.info(f"Starting schema introspection background task for database: {database_name}")
        
        # Introspect Oracle schema
        schema_graph = await schema_introspector.introspect_oracle_schema(schema_name, database_name)
        
        # Store in Neo4j
        await schema_introspector.store_schema_in_neo4j(schema_graph, database_name)
        
        logger.info(f"Schema introspection completed successfully for database: {database_name}")
        
    except Exception as e:
        logger.error(f"Schema introspection background task failed for database: {database_name}: {e}")


@app.get("/schema/search")
async def search_schema_endpoint(
    query: str,
    similarity_threshold: float = 0.6,
    database_name: str = None
):
    """
    Endpoint to search for relevant schema based on query terms.
    
    Useful for exploring what tables and columns are available for a given query.
    """
    try:
        if database_name is None:
            database_name = settings.default_database_name
            
        logger.info(f"Searching schema for: {query} in database: {database_name}")
        
        results = await schema_introspector.find_relevant_schema(
            query, similarity_threshold, database_name
        )
        
        return {
            "query": query,
            "similarity_threshold": similarity_threshold,
            "database_name": database_name,
            "results": results,
            "count": len(results)
        }
        
    except Exception as e:
        logger.error(f"Schema search failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/schema/context")
async def get_schema_context_endpoint(
    table_names: str,
    database_name: str = None
):
    """
    Endpoint to get complete schema context for specific tables.
    
    Args:
        table_names: Comma-separated list of table names
        database_name: Target database name (optional)
    """
    try:
        if database_name is None:
            database_name = settings.default_database_name
            
        logger.info(f"Getting schema context for tables: {table_names} in database: {database_name}")
        
        table_list = [name.strip().upper() for name in table_names.split(',')]
        
        context = await schema_introspector.get_schema_context(table_list, database_name)
        
        return {
            "table_names": table_list,
            "database_name": database_name,
            "context": context
        }
        
    except Exception as e:
        logger.error(f"Get schema context failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/schema/inferred-relationships")
async def get_inferred_relationships_endpoint(database_name: str = None):
    """
    Endpoint to get all inferred foreign key relationships.
    
    Returns relationships that were inferred from naming conventions
    along with confidence scores and statistics.
    
    Args:
        database_name: Target database name (optional)
    """
    try:
        if database_name is None:
            database_name = settings.default_database_name
            
        logger.info(f"Getting inferred foreign key relationships for database: {database_name}")
        
        validation_results = await schema_introspector.validate_inferred_relationships(database_name)
        
        return {
            "message": "Inferred foreign key relationships retrieved successfully",
            "database_name": database_name,
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
        
        metrics = {
            "database_health": db_health,
            "agent_health": "healthy" if agent_healthy else "unhealthy",
            "uptime": "running",
            "version": "2.1.0"
        }
        
        # Add A2A metrics
        a2a_healthy = await a2a_health_check()
        agent_executor = get_agent_executor()
        metrics["a2a_agent_health"] = "healthy" if a2a_healthy else "unhealthy"
        metrics["a2a_active_tasks"] = len(agent_executor.tasks) if agent_executor else 0
        
        return metrics
        
    except Exception as e:
        logger.error(f"Metrics endpoint failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ========================================
# A2A SDK ENDPOINTS
# ========================================

@app.get("/a2a/agent-card")
async def get_a2a_agent_card():
    """
    Get the A2A agent card describing capabilities.
    
    Returns the agent card using the official A2A SDK format.
    """
    try:
        agent_executor = get_agent_executor()
        if not agent_executor:
            raise HTTPException(status_code=500, detail="Agent executor not available")
        
        capabilities = agent_executor.get_capabilities()
        return capabilities
        
    except Exception as e:
        logger.error(f"Failed to get agent card: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/a2a/message")
async def send_a2a_message(request: Dict[str, Any]):
    """
    Send a message to the A2A agent.
    
    This endpoint accepts messages in the A2A format and
    returns responses in the same format.
    """
    try:
        agent_executor = get_agent_executor()
        if not agent_executor:
            raise HTTPException(status_code=500, detail="Agent executor not available")
        
        logger.info("Received A2A message request")
        
        # Create a TaskRequest from the incoming request
        # This is a simplified version - in real implementation,
        # you would use the actual A2A SDK classes
        task_request = type('TaskRequest', (), {
            'message': type('Message', (), {
                'parts': [
                    type('Part', (), {
                        'type': 'text',
                        'text': request.get('message', '')
                    })()
                ]
            })()
        })()
        
        # Process the request
        response = await agent_executor.invoke(task_request)
        
        # Return the response in A2A format
        return {
            "task_id": response.task_id,
            "status": response.status,
            "message": {
                "message_id": response.message.message_id,
                "parts": [
                    {
                        "type": part.type,
                        "text": getattr(part, 'text', None),
                        "name": getattr(part, 'name', None),
                        "result": getattr(part, 'result', None)
                    }
                    for part in response.message.parts
                ],
                "role": response.message.role,
                "timestamp": response.message.timestamp
            }
        }
        
    except Exception as e:
        logger.error(f"A2A message failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/a2a/task/{task_id}")
async def get_a2a_task_status(task_id: str):
    """
    Get the status of an A2A task.
    """
    try:
        agent_executor = get_agent_executor()
        if not agent_executor:
            raise HTTPException(status_code=500, detail="Agent executor not available")
        
        task_info = await agent_executor.get_task_status(task_id)
        if not task_info:
            raise HTTPException(status_code=404, detail="Task not found")
        
        return {
            "task_id": task_info.task_id,
            "status": task_info.status,
            "created_at": task_info.created_at.isoformat(),
            "updated_at": task_info.updated_at.isoformat(),
            "error": task_info.error
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get task status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/a2a/status")
async def get_a2a_service_status():
    """
    Get the status of the A2A service.
    """
    try:
        agent_executor = get_agent_executor()
        if not agent_executor:
            return {
                "available": False,
                "message": "A2A agent executor not initialized"
            }
        
        is_healthy = agent_executor.initialized
        
        return {
            "available": True,
            "healthy": is_healthy,
            "agent_initialized": agent_executor.initialized,
            "active_tasks": len(agent_executor.tasks)
        }
        
    except Exception as e:
        logger.error(f"Failed to get A2A service status: {e}")
        return {
            "available": False,
            "message": f"Error checking service status: {str(e)}"
        }


if __name__ == "__main__":
    # Run the application
    uvicorn.run(
        "main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.debug,
        log_level="info"
    ) 