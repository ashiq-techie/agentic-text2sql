"""
FastAPI application for the text-to-SQL agent.
"""
import logging
from contextlib import asynccontextmanager
from typing import List, Dict, Any
import uvicorn
from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import time

from config import settings
from schemas import (
    ChatRequest, ChatResponse, HealthResponse, 
    ChatMessage, AgentResponse
)
from clients import initialize_clients, shutdown_clients, health_check_all
from agent import process_chat_request, agent_health_check
from schema_introspection import schema_introspector

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    logger.info("Starting text-to-SQL agent application")
    
    try:
        # Initialize database clients
        await initialize_clients()
        
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
    title="Text-to-SQL Agent",
    description="Advanced text-to-SQL agent using Neo4j knowledge graph and LangGraph",
    version="1.0.0",
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
        "message": "Text-to-SQL Agent API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health"
    }


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    try:
        # Check database connections
        db_health = await health_check_all()
        
        # Check agent health
        agent_healthy = await agent_health_check()
        
        # Overall health status
        all_healthy = (
            all(status == "healthy" for status in db_health.values()) and
            agent_healthy
        )
        
        return HealthResponse(
            status="healthy" if all_healthy else "unhealthy",
            dependencies={
                **db_health,
                "agent": "healthy" if agent_healthy else "unhealthy"
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
    Main chat endpoint for text-to-SQL conversion.
    
    Accepts a list of chat messages and returns the agent's response with SQL query results.
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


@app.get("/metrics")
async def get_metrics():
    """
    Endpoint to get basic application metrics.
    """
    try:
        # Get database health
        db_health = await health_check_all()
        
        # Get agent health
        agent_healthy = await agent_health_check()
        
        return {
            "database_health": db_health,
            "agent_health": "healthy" if agent_healthy else "unhealthy",
            "uptime": "running",  # Could be enhanced with actual uptime
            "version": "1.0.0"
        }
        
    except Exception as e:
        logger.error(f"Metrics endpoint failed: {e}")
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