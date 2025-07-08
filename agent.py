"""
LangGraph React Agent for Text-to-SQL conversion with Neo4j schema knowledge graph.
"""
import logging
from typing import Dict, Any, List, Optional, Tuple
from typing_extensions import TypedDict
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import MemorySaver
import json
import time

from config import settings
from schemas import ChatMessage, AgentResponse, QueryResult
from agent_tools import AGENT_TOOLS, get_tools_description

logger = logging.getLogger(__name__)


class AgentState(TypedDict):
    """State model for the agent - required fields for create_react_agent."""
    messages: List[Dict[str, Any]]
    remaining_steps: int


SYSTEM_PROMPT = """
You are an expert Text-to-SQL agent specialized in converting natural language queries into accurate SQL statements using Oracle database schema information stored in a Neo4j knowledge graph. You support multiple Oracle databases and can help users query specific databases.

## Your Role
You help users query Oracle databases by:
1. Understanding their natural language questions
2. Identifying the target database (if specified)
3. Finding relevant tables and columns using fuzzy matching
4. Analyzing database schema and relationships
5. Generating accurate SQL queries
6. Executing queries and presenting results

## Available Tools
{tools_description}

## Multi-Database Support
This system supports multiple Oracle databases. When users specify a database name or when working with specific databases:
- Use the database_name parameter in schema_search and get_schema_context tools
- If no database is specified, the system uses the default database
- Database names should be passed exactly as specified by the user
- Always include the database name in your responses when relevant

## Knowledge Graph Schema
The Neo4j database contains Oracle database schemas structured as:
- Database nodes (type: 'database') - represent different Oracle databases
- Table nodes (type: 'table') connected via HAS_TABLE relationships
- Column nodes (type: 'column') connected via HAS_COLUMN relationships  
- Foreign key relationships via HAS_FOREIGN_KEY between columns

## Workflow Process
Follow this systematic approach:

1. **UNDERSTAND THE QUERY**
   - Parse the user's natural language question
   - Identify key business concepts, entities, and requirements
   - Determine what data the user wants to retrieve
   - Check if the user specified a particular database name

2. **FIND RELEVANT SCHEMA**
   - Use schema_search tool to find tables and columns related to the query
   - Include database_name parameter if specified by user
   - Consider fuzzy matching for abbreviated names (e.g., 'Lifecycle' -> 'LFC')
   - Search for multiple related concepts if needed

3. **ANALYZE SCHEMA CONTEXT**
   - Use get_schema_context tool to get complete information about relevant tables
   - Include database_name parameter to ensure you get the right database's schema
   - Understand column data types, constraints, and relationships
   - Identify foreign key relationships between tables

4. **GENERATE SQL QUERY**
   - Write accurate SQL based on the schema analysis
   - Use proper table and column names as identified
   - Include necessary JOINs based on foreign key relationships
   - Add appropriate WHERE clauses, ORDER BY, and LIMIT clauses
   - Always limit results for performance (use ROWNUM or FETCH FIRST)

5. **EXECUTE AND VALIDATE**
   - Execute the SQL query using oracle_query tool
   - Validate results and handle any errors
   - Provide clear explanations of what the query does
   - Mention which database the results came from

## Important Guidelines

**Database Selection:**
- Pay attention to database names mentioned by users (e.g., "prod_db", "staging", "dev")
- When using schema_search or get_schema_context tools, include database_name parameter if specified
- If unsure about database name, ask the user or use the default
- Always mention which database you're querying in your responses

**Tool Usage:**
- schema_search: Include database_name parameter when known
- get_schema_context: Include database_name parameter when known  
- neo4j_query: Use to explore schema structure across databases
- oracle_query: Execute final SQL queries (uses connection routing)
  - Supports multiple output formats: json (default), csv, parquet, html, summary
  - Use format parameter to specify desired output format
  - Use "summary" format for natural language results with statistics

**Query Generation:**
- Always use exact table and column names from schema analysis
- Use proper Oracle SQL syntax
- Include table aliases for readability
- Limit results to reasonable sizes (≤1000 rows typically)
- Use parameterized queries when possible

**Error Handling:**
- If a query fails, analyze the error and try alternative approaches
- Check for typos in table/column names
- Verify JOIN conditions and data types
- Consider if the wrong database was targeted
- Provide helpful error explanations to users

**Performance:**
- Always include ROWNUM or FETCH FIRST clauses to limit results
- Use indexes when available (check schema context)
- Prefer specific columns over SELECT *
- Consider query complexity and execution time

**Communication:**
- Explain your reasoning and steps clearly
- Show the SQL query before executing it
- Mention which database you're querying
- Provide context about what the results mean
- Offer suggestions for query modifications if needed

## Example Interactions

**User:** "Show me all active users in the prod_db database"
**Process:**
1. Identify target database: prod_db
2. Search for "user" and "active" in schema using database_name="prod_db"
3. Find USER or USERS table with STATUS column in prod_db
4. Generate: SELECT * FROM USERS WHERE STATUS = 'ACTIVE' AND ROWNUM <= 100
5. Execute using oracle_query tool with format="json" (default) and present results, mentioning they're from prod_db

**User:** "How many orders were placed last month?"
**Process:**
1. No specific database mentioned, use default
2. Search for "order" and date-related columns
3. Find ORDERS table with ORDER_DATE column
4. Generate: SELECT COUNT(*) FROM ORDERS WHERE ORDER_DATE >= ADD_MONTHS(SYSDATE, -1)
5. Execute and present count

**User:** "Compare user counts between staging and prod databases"
**Process:**
1. Query staging database: use database_name="staging" in tools
2. Query prod database: use database_name="prod" in tools
3. Generate separate queries for each database
4. Present comparison results

**User:** "Export customer data to CSV format"
**Process:**
1. Search for "customer" in schema
2. Find CUSTOMERS table with relevant columns
3. Generate: SELECT * FROM CUSTOMERS WHERE ROWNUM <= 1000
4. Execute using oracle_query tool with format="csv"
5. Present CSV data with proper content type indication

**User:** "Give me a summary of recent sales data"
**Process:**
1. Search for "sales" and date-related columns
2. Find SALES table with DATE columns
3. Generate: SELECT * FROM SALES WHERE SALE_DATE >= SYSDATE - 30
4. Execute using oracle_query tool with format="summary"
5. Present natural language summary with statistics and insights

**User:** "Show me user data in a table format for the report"
**Process:**
1. Search for "user" in schema
2. Find USERS table
3. Generate: SELECT USER_ID, USER_NAME, EMAIL, STATUS FROM USERS WHERE ROWNUM <= 50
4. Execute using oracle_query tool with format="html"
5. Present HTML table ready for embedding in reports

## Format Usage Guidelines

**When to use different formats:**
- **json** (default): For API responses, web applications, general use
- **csv**: When user requests export, Excel compatibility, or data analysis
- **parquet**: For large datasets, efficient storage, or data science workflows
- **html**: For reports, browser display, or formatted presentation
- **summary**: When user wants insights, statistics, or natural language explanation

**Format Selection:**
- Listen for user cues: "export", "CSV", "summary", "report", "table"
- For large datasets (>100 rows), suggest CSV or parquet
- For analytical queries, offer summary format
- Always explain the format choice to users

Remember: Always use the tools systematically, specify database names when known, choose appropriate output formats based on user needs, and provide clear, accurate results with proper explanations including database context.
"""


class Text2SQLAgent:
    """Text-to-SQL agent using LangGraph React pattern."""
    
    def __init__(self):
        self.llm = ChatOpenAI(
            model=settings.openai_model,
            temperature=0.1,
            api_key=settings.openai_api_key,
            streaming=True
        )
        self.memory = MemorySaver()
        self.agent = None
        self._initialize_agent()
    
    def _initialize_agent(self):
        """Initialize the React agent with tools and system prompt."""
        try:
            system_prompt = SYSTEM_PROMPT.format(
                tools_description=get_tools_description()
            )
            
            self.agent = create_react_agent(
                self.llm,
                AGENT_TOOLS,
                prompt=system_prompt,
                checkpointer=self.memory,
                state_schema=AgentState
            )
            
            logger.info("Text-to-SQL agent initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize agent: {e}")
            raise
    
    async def process_query(self, messages: List[ChatMessage], session_id: Optional[str] = None) -> AgentResponse:
        """Process a user query through the agent."""
        start_time = time.time()
        
        try:
            logger.info(f"Processing query for session: {session_id}")
            
            # Convert messages to LangChain format
            langchain_messages = []
            for msg in messages:
                if msg.role == "user":
                    langchain_messages.append(HumanMessage(content=msg.content))
                elif msg.role == "assistant":
                    langchain_messages.append(AIMessage(content=msg.content))
                elif msg.role == "system":
                    langchain_messages.append(SystemMessage(content=msg.content))
            
            # Configure thread for session management
            thread_config = {
                "configurable": {"thread_id": session_id or "default"}
            }
            
            # Process through agent
            response = await self._run_agent(langchain_messages, thread_config)
            
            execution_time = time.time() - start_time
            
            # Parse the response to extract SQL query results if any
            query_results = self._extract_query_results(response)
            
            return AgentResponse(
                message=response,
                query_results=query_results,
                execution_time=execution_time,
                session_id=session_id
            )
            
        except Exception as e:
            logger.error(f"Error processing query: {e}")
            execution_time = time.time() - start_time
            
            return AgentResponse(
                message=f"I apologize, but I encountered an error while processing your query: {str(e)}",
                execution_time=execution_time,
                session_id=session_id
            )
    
    async def _run_agent(self, messages: List, thread_config: Dict[str, Any]) -> str:
        """Run the agent with the given messages."""
        try:
            # Execute the agent
            result = await self.agent.ainvoke(
                {"messages": messages},
                config=thread_config
            )
            
            # Extract the final message content
            if "messages" in result and result["messages"]:
                last_message = result["messages"][-1]
                return last_message.content
            else:
                return "I'm sorry, I couldn't process your query at this time."
                
        except Exception as e:
            logger.error(f"Agent execution failed: {e}")
            raise
    
    def _extract_query_results(self, response: str) -> Optional[QueryResult]:
        """Extract SQL query results from the agent response."""
        try:
            # Look for JSON blocks in the response that contain query results
            import re
            
            # Find JSON blocks that look like query results
            json_pattern = r'```json\s*(\{.*?"success":\s*true.*?\})\s*```'
            matches = re.findall(json_pattern, response, re.DOTALL)
            
            for match in matches:
                try:
                    data = json.loads(match)
                    if data.get("success"):
                        # Handle different formats
                        if "results" in data:
                            # Standard JSON format
                            return QueryResult(
                                query=data.get("query", ""),
                                results=data.get("results", []),
                                execution_time=data.get("execution_time", 0.0),
                                row_count=data.get("row_count", 0)
                            )
                        elif "summary" in data:
                            # Summary format - convert to compatible format
                            return QueryResult(
                                query=data.get("query", ""),
                                results=[{"summary": data.get("summary", ""), "statistics": data.get("statistics", {})}],
                                execution_time=data.get("execution_time", 0.0),
                                row_count=data.get("row_count", 0)
                            )
                        elif "data" in data:
                            # CSV, HTML, or Parquet format - store as metadata
                            return QueryResult(
                                query=data.get("query", ""),
                                results=[{
                                    "format": data.get("format", "unknown"),
                                    "data": data.get("data", ""),
                                    "content_type": data.get("content_type", ""),
                                    "encoding": data.get("encoding", "")
                                }],
                                execution_time=data.get("execution_time", 0.0),
                                row_count=data.get("row_count", 0)
                            )
                except json.JSONDecodeError:
                    continue
            
            return None
            
        except Exception as e:
            logger.error(f"Error extracting query results: {e}")
            return None
    
    async def health_check(self) -> bool:
        """Check if the agent is healthy and can process queries."""
        try:
            test_messages = [HumanMessage(content="Hello, can you help me with a SQL query?")]
            thread_config = {"configurable": {"thread_id": "health_check"}}
            
            response = await self._run_agent(test_messages, thread_config)
            return "help" in response.lower() or "sql" in response.lower()
            
        except Exception as e:
            logger.error(f"Agent health check failed: {e}")
            return False


# Global agent instance
text2sql_agent = Text2SQLAgent()





async def process_chat_request(messages: List[ChatMessage], session_id: Optional[str] = None) -> AgentResponse:
    """Process a chat request through the text-to-SQL agent."""
    return await text2sql_agent.process_query(messages, session_id)


async def agent_health_check() -> bool:
    """Check if the agent is healthy."""
    return await text2sql_agent.health_check() 