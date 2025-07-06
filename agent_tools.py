"""
Agent tools for Neo4j and Oracle query execution.
"""
import logging
from typing import Dict, Any, List, Optional
from langchain.tools import BaseTool
from pydantic import BaseModel, Field
from clients import neo4j_client, oracle_client
from schema_introspection import schema_introspector
import json
import time

logger = logging.getLogger(__name__)


class Neo4jQueryInput(BaseModel):
    """Input schema for Neo4j query tool."""
    query: str = Field(..., description="Cypher query to execute")
    parameters: Optional[Dict[str, Any]] = Field(default=None, description="Query parameters")


class OracleQueryInput(BaseModel):
    """Input schema for Oracle query tool."""
    query: str = Field(..., description="SQL query to execute")
    parameters: Optional[Dict[str, Any]] = Field(default=None, description="Query parameters")


class SchemaSearchInput(BaseModel):
    """Input schema for schema search tool."""
    search_terms: str = Field(..., description="Search terms to find relevant tables and columns")
    similarity_threshold: Optional[float] = Field(default=0.6, description="Similarity threshold for fuzzy matching")


class Neo4jQueryTool(BaseTool):
    """Tool for executing Neo4j queries."""
    
    name: str = "neo4j_query"
    description: str = """
    Execute Cypher queries against the Neo4j knowledge graph containing database schema information.
    Use this tool to:
    - Find relevant tables and columns based on search terms
    - Understand table relationships and foreign keys
    - Get schema context for SQL query generation
    
    The knowledge graph structure:
    - Database nodes (type: 'database')
    - Table nodes (type: 'table') connected via HAS_TABLE relationships
    - Column nodes (type: 'column') connected via HAS_COLUMN relationships
    - Foreign key relationships via HAS_FOREIGN_KEY between columns
    
    Example queries:
    - Find tables: MATCH (t:SchemaNode {type: 'table'}) WHERE t.name CONTAINS 'user' RETURN t
    - Find columns: MATCH (c:SchemaNode {type: 'column'}) WHERE c.name CONTAINS 'name' RETURN c
    - Get table schema: MATCH (t:SchemaNode {type: 'table', name: 'USERS'})-[:RELATIONSHIP {type: 'HAS_COLUMN'}]->(c:SchemaNode) RETURN c
    """
    args_schema: type = Neo4jQueryInput
    
    async def _arun(self, query: str, parameters: Optional[Dict[str, Any]] = None) -> str:
        """Execute Neo4j query asynchronously."""
        try:
            start_time = time.time()
            logger.info(f"Executing Neo4j query: {query}")
            
            if parameters is None:
                parameters = {}
            
            results = await neo4j_client.query(query, parameters)
            execution_time = time.time() - start_time
            
            response = {
                "success": True,
                "results": results,
                "execution_time": execution_time,
                "row_count": len(results)
            }
            
            logger.info(f"Neo4j query completed in {execution_time:.3f}s, returned {len(results)} results")
            return json.dumps(response, indent=2)
            
        except Exception as e:
            logger.error(f"Neo4j query failed: {e}")
            return json.dumps({
                "success": False,
                "error": str(e),
                "query": query,
                "parameters": parameters
            }, indent=2)
    
    def _run(self, query: str, parameters: Optional[Dict[str, Any]] = None) -> str:
        """Synchronous version (not used in async context)."""
        raise NotImplementedError("Use async version")


class OracleQueryTool(BaseTool):
    """Tool for executing Oracle SQL queries."""
    
    name: str = "oracle_query"
    description: str = """
    Execute SQL queries against the Oracle database.
    Use this tool to:
    - Execute the final SQL query generated based on schema analysis
    - Retrieve actual data from the database
    - Test query validity and performance
    
    IMPORTANT: 
    - Always use parameterized queries to prevent SQL injection
    - Limit results using ROWNUM or FETCH FIRST clauses for large datasets
    - Use proper table and column names as identified from schema analysis
    
    Example usage:
    - SELECT * FROM USERS WHERE ROWNUM <= 10
    - SELECT u.USER_ID, u.USER_NAME FROM USERS u WHERE u.STATUS = 'ACTIVE'
    """
    args_schema: type = OracleQueryInput
    
    async def _arun(self, query: str, parameters: Optional[Dict[str, Any]] = None) -> str:
        """Execute Oracle query asynchronously."""
        try:
            start_time = time.time()
            logger.info(f"Executing Oracle query: {query}")
            
            if parameters is None:
                parameters = {}
            
            results = await oracle_client.query(query, parameters)
            execution_time = time.time() - start_time
            
            response = {
                "success": True,
                "results": results,
                "execution_time": execution_time,
                "row_count": len(results)
            }
            
            logger.info(f"Oracle query completed in {execution_time:.3f}s, returned {len(results)} results")
            return json.dumps(response, indent=2)
            
        except Exception as e:
            logger.error(f"Oracle query failed: {e}")
            return json.dumps({
                "success": False,
                "error": str(e),
                "query": query,
                "parameters": parameters
            }, indent=2)
    
    def _run(self, query: str, parameters: Optional[Dict[str, Any]] = None) -> str:
        """Synchronous version (not used in async context)."""
        raise NotImplementedError("Use async version")


class SchemaSearchTool(BaseTool):
    """Tool for searching relevant schema based on natural language query."""
    
    name: str = "schema_search"
    description: str = """
    Search for relevant tables and columns in the database schema based on natural language terms.
    Use this tool to:
    - Find relevant tables and columns for a given query
    - Understand which database objects are related to specific business concepts
    - Get fuzzy matches for abbreviated or similar terms (e.g., 'Lifecycle' -> 'LFC')
    
    This tool uses fuzzy matching to find similar table and column names, which is helpful when:
    - Table names are abbreviated (e.g., USER_LIFECYCLE_STAGE -> ULS)
    - Column names use different naming conventions
    - You need to explore the schema for relevant data
    
    Example usage:
    - Search for "user profile" to find USER_PROFILES table
    - Search for "order status" to find ORDER_STATUS columns
    - Search for "LFC" to find LIFECYCLE related tables
    """
    args_schema: type = SchemaSearchInput
    
    async def _arun(self, search_terms: str, similarity_threshold: float = 0.6) -> str:
        """Search for relevant schema asynchronously."""
        try:
            start_time = time.time()
            logger.info(f"Searching schema for terms: {search_terms}")
            
            relevant_schema = await schema_introspector.find_relevant_schema(
                search_terms, similarity_threshold
            )
            
            execution_time = time.time() - start_time
            
            response = {
                "success": True,
                "relevant_tables": relevant_schema,
                "execution_time": execution_time,
                "search_terms": search_terms,
                "similarity_threshold": similarity_threshold
            }
            
            logger.info(f"Schema search completed in {execution_time:.3f}s, found {len(relevant_schema)} relevant tables")
            return json.dumps(response, indent=2)
            
        except Exception as e:
            logger.error(f"Schema search failed: {e}")
            return json.dumps({
                "success": False,
                "error": str(e),
                "search_terms": search_terms,
                "similarity_threshold": similarity_threshold
            }, indent=2)
    
    def _run(self, search_terms: str, similarity_threshold: float = 0.6) -> str:
        """Synchronous version (not used in async context)."""
        raise NotImplementedError("Use async version")


class GetSchemaContextTool(BaseTool):
    """Tool for getting complete schema context for specific tables."""
    
    name: str = "get_schema_context"
    description: str = """
    Get complete schema context for specific tables including all columns, data types, 
    constraints, and relationships.
    Use this tool to:
    - Get detailed information about specific tables
    - Understand column data types and constraints
    - Find foreign key relationships between tables
    - Get the complete context needed for SQL query generation
    
    This tool provides comprehensive schema information needed to write accurate SQL queries.
    """
    args_schema: type = BaseModel
    
    async def _arun(self, table_names: str) -> str:
        """Get schema context for specified tables."""
        try:
            start_time = time.time()
            
            # Parse table names (expecting comma-separated string)
            table_list = [name.strip().upper() for name in table_names.split(',')]
            logger.info(f"Getting schema context for tables: {table_list}")
            
            schema_context = await schema_introspector.get_schema_context(table_list)
            
            execution_time = time.time() - start_time
            
            response = {
                "success": True,
                "schema_context": schema_context,
                "execution_time": execution_time,
                "table_names": table_list
            }
            
            logger.info(f"Schema context retrieved in {execution_time:.3f}s for {len(table_list)} tables")
            return json.dumps(response, indent=2)
            
        except Exception as e:
            logger.error(f"Get schema context failed: {e}")
            return json.dumps({
                "success": False,
                "error": str(e),
                "table_names": table_names
            }, indent=2)
    
    def _run(self, table_names: str) -> str:
        """Synchronous version (not used in async context)."""
        raise NotImplementedError("Use async version")


# Tool instances
neo4j_query_tool = Neo4jQueryTool()
oracle_query_tool = OracleQueryTool()
schema_search_tool = SchemaSearchTool()
get_schema_context_tool = GetSchemaContextTool()

# List of all tools for the agent
AGENT_TOOLS = [
    schema_search_tool,
    get_schema_context_tool,
    neo4j_query_tool,
    oracle_query_tool
]


def get_tools_description() -> str:
    """Get a description of all available tools."""
    descriptions = []
    for tool in AGENT_TOOLS:
        descriptions.append(f"- {tool.name}: {tool.description}")
    
    return "\n".join(descriptions) 