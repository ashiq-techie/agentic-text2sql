"""
Agent tools for Neo4j and Oracle query execution.
"""
import logging
from typing import Dict, Any, List, Optional, Union
from langchain.tools import BaseTool
from pydantic import BaseModel, Field
from clients import neo4j_client, oracle_client
from schema_introspection import schema_introspector
import json
import time
import pandas as pd
import io

logger = logging.getLogger(__name__)


class Neo4jQueryInput(BaseModel):
    """Input schema for Neo4j query tool."""
    query: str = Field(..., description="Cypher query to execute")
    parameters: Optional[Dict[str, Any]] = Field(default=None, description="Query parameters")


class OracleQueryInput(BaseModel):
    """Input schema for Oracle query tool."""
    query: str = Field(..., description="SQL query to execute")
    parameters: Optional[Dict[str, Any]] = Field(default=None, description="Query parameters")
    format: str = Field(default="json", description="Output format: json, csv, parquet, html, or summary")


class SchemaSearchInput(BaseModel):
    """Input schema for schema search tool."""
    search_terms: str = Field(..., description="Search terms to find relevant tables and columns")
    similarity_threshold: Optional[float] = Field(default=0.6, description="Similarity threshold for fuzzy matching")
    database_name: Optional[str] = Field(default=None, description="Database name to search in")


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
    """Tool for executing Oracle SQL queries with multiple output formats."""
    
    name: str = "oracle_query"
    description: str = """
    Execute SQL queries against the Oracle database with configurable output formats.
    Use this tool to:
    - Execute the final SQL query generated based on schema analysis
    - Retrieve actual data from the database in various formats
    - Test query validity and performance
    - Get data summaries and statistics
    
    IMPORTANT: 
    - Always use parameterized queries to prevent SQL injection
    - Limit results using ROWNUM or FETCH FIRST clauses for large datasets
    - Use proper table and column names as identified from schema analysis
    
    Available output formats:
    - json (default): Standard JSON format, compatible with all clients
    - csv: Comma-separated values, Excel-compatible
    - parquet: Compressed binary format, efficient for large datasets
    - html: HTML table format, browser-ready
    - summary: Natural language summary with statistics
    
    Example usage:
    - SELECT * FROM USERS WHERE ROWNUM <= 10 (format: json)
    - SELECT u.USER_ID, u.USER_NAME FROM USERS u WHERE u.STATUS = 'ACTIVE' (format: csv)
    - SELECT COUNT(*) FROM ORDERS WHERE ORDER_DATE >= SYSDATE - 30 (format: summary)
    """
    args_schema: type = OracleQueryInput
    
    def _convert_to_format(self, results: List[Dict[str, Any]], format: str, query: str, execution_time: float) -> Union[str, bytes]:
        """Convert query results to the specified format."""
        try:
            if format == "json":
                return json.dumps({
                    "success": True,
                    "results": results,
                    "execution_time": execution_time,
                    "row_count": len(results),
                    "query": query,
                    "format": format
                }, indent=2)
            
            if not results:
                return json.dumps({
                    "success": True,
                    "results": [],
                    "execution_time": execution_time,
                    "row_count": 0,
                    "query": query,
                    "format": format,
                    "message": "Query executed successfully but returned no results"
                }, indent=2)
            
            # Convert to pandas DataFrame
            df = pd.DataFrame(results)
            
            if format == "csv":
                csv_output = df.to_csv(index=False)
                return json.dumps({
                    "success": True,
                    "data": csv_output,
                    "execution_time": execution_time,
                    "row_count": len(results),
                    "query": query,
                    "format": format,
                    "content_type": "text/csv"
                }, indent=2)
            
            elif format == "parquet":
                buffer = io.BytesIO()
                df.to_parquet(buffer, index=False)
                parquet_bytes = buffer.getvalue()
                # Convert bytes to base64 for JSON serialization
                import base64
                parquet_b64 = base64.b64encode(parquet_bytes).decode('utf-8')
                
                return json.dumps({
                    "success": True,
                    "data": parquet_b64,
                    "execution_time": execution_time,
                    "row_count": len(results),
                    "query": query,
                    "format": format,
                    "content_type": "application/octet-stream",
                    "encoding": "base64"
                }, indent=2)
            
            elif format == "html":
                html_output = df.to_html(index=False, classes="table table-striped table-bordered", escape=False)
                return json.dumps({
                    "success": True,
                    "data": html_output,
                    "execution_time": execution_time,
                    "row_count": len(results),
                    "query": query,
                    "format": format,
                    "content_type": "text/html"
                }, indent=2)
            
            elif format == "summary":
                # Generate natural language summary
                summary = self._generate_summary(df, query, execution_time)
                return json.dumps({
                    "success": True,
                    "summary": summary,
                    "statistics": self._generate_statistics(df),
                    "execution_time": execution_time,
                    "row_count": len(results),
                    "query": query,
                    "format": format
                }, indent=2)
            
            else:
                # Invalid format, return json with error
                return json.dumps({
                    "success": False,
                    "error": f"Unsupported format: {format}. Available formats: json, csv, parquet, html, summary",
                    "query": query,
                    "format": format
                }, indent=2)
                
        except Exception as e:
            logger.error(f"Error converting to format {format}: {e}")
            return json.dumps({
                "success": False,
                "error": f"Failed to convert to {format}: {str(e)}",
                "query": query,
                "format": format
            }, indent=2)
    
    def _generate_summary(self, df: pd.DataFrame, query: str, execution_time: float) -> str:
        """Generate a natural language summary of the query results."""
        try:
            row_count = len(df)
            col_count = len(df.columns)
            
            summary = f"Query executed successfully in {execution_time:.3f} seconds. "
            summary += f"Retrieved {row_count} rows with {col_count} columns: {', '.join(df.columns)}. "
            
            if row_count > 0:
                # Add some basic insights
                if row_count == 1:
                    summary += "Found 1 record matching your criteria. "
                else:
                    summary += f"Found {row_count} records matching your criteria. "
                
                # Sample data
                if row_count <= 5:
                    summary += "All results are shown in the data. "
                else:
                    summary += f"First few rows: {df.head(3).to_dict('records')}. "
                
                # Basic statistics for numeric columns
                numeric_cols = df.select_dtypes(include=['number']).columns
                if len(numeric_cols) > 0:
                    summary += f"Numeric columns ({', '.join(numeric_cols)}) have the following ranges: "
                    for col in numeric_cols:
                        min_val = df[col].min()
                        max_val = df[col].max()
                        summary += f"{col}: {min_val} to {max_val}. "
            else:
                summary += "No records found matching your criteria. "
            
            return summary
            
        except Exception as e:
            return f"Query executed successfully but failed to generate summary: {str(e)}"
    
    def _generate_statistics(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Generate statistical information about the results."""
        try:
            stats = {
                "row_count": len(df),
                "column_count": len(df.columns),
                "columns": list(df.columns),
                "data_types": df.dtypes.to_dict(),
                "memory_usage": df.memory_usage(deep=True).sum(),
                "null_counts": df.isnull().sum().to_dict()
            }
            
            # Add statistics for numeric columns
            numeric_cols = df.select_dtypes(include=['number']).columns
            if len(numeric_cols) > 0:
                stats["numeric_summary"] = df[numeric_cols].describe().to_dict()
            
            # Add statistics for text columns
            text_cols = df.select_dtypes(include=['object']).columns
            if len(text_cols) > 0:
                stats["text_summary"] = {}
                for col in text_cols:
                    stats["text_summary"][col] = {
                        "unique_values": df[col].nunique(),
                        "most_common": df[col].value_counts().head(5).to_dict()
                    }
            
            return stats
            
        except Exception as e:
            return {"error": f"Failed to generate statistics: {str(e)}"}
    
    async def _arun(self, query: str, parameters: Optional[Dict[str, Any]] = None, format: str = "json") -> str:
        """Execute Oracle query asynchronously with format support."""
        try:
            start_time = time.time()
            logger.info(f"Executing Oracle query: {query} (format: {format})")
            
            if parameters is None:
                parameters = {}
            
            results = await oracle_client.query(query, parameters)
            execution_time = time.time() - start_time
            
            # Convert to requested format
            formatted_response = self._convert_to_format(results, format, query, execution_time)
            
            logger.info(f"Oracle query completed in {execution_time:.3f}s, returned {len(results)} results in {format} format")
            return formatted_response
            
        except Exception as e:
            logger.error(f"Oracle query failed: {e}")
            return json.dumps({
                "success": False,
                "error": str(e),
                "query": query,
                "parameters": parameters,
                "format": format
            }, indent=2)
    
    def _run(self, query: str, parameters: Optional[Dict[str, Any]] = None, format: str = "json") -> str:
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
    
    async def _arun(self, search_terms: str, similarity_threshold: float = 0.6, database_name: str = None) -> str:
        """Search for relevant schema asynchronously."""
        try:
            start_time = time.time()
            logger.info(f"Searching schema for terms: {search_terms} in database: {database_name}")
            
            relevant_schema = await schema_introspector.find_relevant_schema(
                search_terms, similarity_threshold, database_name
            )
            
            execution_time = time.time() - start_time
            
            response = {
                "success": True,
                "relevant_tables": relevant_schema,
                "execution_time": execution_time,
                "search_terms": search_terms,
                "similarity_threshold": similarity_threshold,
                "database_name": database_name
            }
            
            logger.info(f"Schema search completed in {execution_time:.3f}s, found {len(relevant_schema)} relevant tables")
            return json.dumps(response, indent=2)
            
        except Exception as e:
            logger.error(f"Schema search failed: {e}")
            return json.dumps({
                "success": False,
                "error": str(e),
                "search_terms": search_terms,
                "similarity_threshold": similarity_threshold,
                "database_name": database_name
            }, indent=2)
    
    def _run(self, search_terms: str, similarity_threshold: float = 0.6) -> str:
        """Synchronous version (not used in async context)."""
        raise NotImplementedError("Use async version")


class GetSchemaContextInput(BaseModel):
    """Input schema for get schema context tool."""
    table_names: str = Field(..., description="Comma-separated list of table names")
    database_name: Optional[str] = Field(default=None, description="Database name to get context from")


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
    args_schema: type = GetSchemaContextInput
    
    async def _arun(self, table_names: str, database_name: str = None) -> str:
        """Get schema context for specified tables."""
        try:
            start_time = time.time()
            
            # Parse table names (expecting comma-separated string)
            table_list = [name.strip().upper() for name in table_names.split(',')]
            logger.info(f"Getting schema context for tables: {table_list} in database: {database_name}")
            
            schema_context = await schema_introspector.get_schema_context(table_list, database_name)
            
            execution_time = time.time() - start_time
            
            response = {
                "success": True,
                "schema_context": schema_context,
                "execution_time": execution_time,
                "table_names": table_list,
                "database_name": database_name
            }
            
            logger.info(f"Schema context retrieved in {execution_time:.3f}s for {len(table_list)} tables")
            return json.dumps(response, indent=2)
            
        except Exception as e:
            logger.error(f"Get schema context failed: {e}")
            return json.dumps({
                "success": False,
                "error": str(e),
                "table_names": table_names,
                "database_name": database_name
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