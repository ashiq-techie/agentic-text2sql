"""
LangGraph React Agent for Text-to-SQL conversion with Neo4j schema knowledge graph.
"""
import logging
from typing import Dict, Any, List, Optional, Tuple
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from pydantic import BaseModel, Field
import json
import time
import asyncio

from config import settings
from schemas import ChatMessage, AgentResponse, QueryResult
from agent_tools import AGENT_TOOLS, get_tools_description

logger = logging.getLogger(__name__)


class AgentState(BaseModel):
    """State model for the agent."""
    messages: List[Dict[str, Any]] = Field(default_factory=list)
    user_query: str = Field(default="")
    session_id: Optional[str] = Field(default=None)
    relevant_tables: List[str] = Field(default_factory=list)
    schema_context: Optional[Dict[str, Any]] = Field(default=None)
    sql_query: Optional[str] = Field(default=None)
    query_results: Optional[Dict[str, Any]] = Field(default=None)
    error_message: Optional[str] = Field(default=None)
    execution_time: float = Field(default=0.0)


SYSTEM_PROMPT = """
You are an expert Text-to-SQL agent specialized in converting natural language queries into accurate SQL statements using Oracle database schema information stored in a Neo4j knowledge graph.

## Your Role
You help users query Oracle databases by:
1. Understanding their natural language questions
2. Finding relevant tables and columns using fuzzy matching
3. Analyzing database schema and relationships
4. Generating accurate SQL queries
5. Executing queries and presenting results

## Available Tools
{tools_description}

## Knowledge Graph Schema
The Neo4j database contains the Oracle database schema structured as:
- Database nodes (type: 'database')
- Table nodes (type: 'table') connected via HAS_TABLE relationships
- Column nodes (type: 'column') connected via HAS_COLUMN relationships  
- Foreign key relationships via HAS_FOREIGN_KEY between columns

## Workflow Process
Follow this systematic approach:

1. **UNDERSTAND THE QUERY**
   - Parse the user's natural language question
   - Identify key business concepts, entities, and requirements
   - Determine what data the user wants to retrieve

2. **FIND RELEVANT SCHEMA**
   - Use schema_search tool to find tables and columns related to the query
   - Consider fuzzy matching for abbreviated names (e.g., 'Lifecycle' -> 'LFC')
   - Search for multiple related concepts if needed

3. **ANALYZE SCHEMA CONTEXT**
   - Use get_schema_context tool to get complete information about relevant tables
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

## Important Guidelines

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
- Provide helpful error explanations to users

**Performance:**
- Always include ROWNUM or FETCH FIRST clauses to limit results
- Use indexes when available (check schema context)
- Prefer specific columns over SELECT *
- Consider query complexity and execution time

**Communication:**
- Explain your reasoning and steps clearly
- Show the SQL query before executing it
- Provide context about what the results mean
- Offer suggestions for query modifications if needed

## Example Interactions

**User:** "Show me all active users"
**Process:**
1. Search for "user" and "active" in schema
2. Find USER or USERS table with STATUS column
3. Generate: SELECT * FROM USERS WHERE STATUS = 'ACTIVE' AND ROWNUM <= 100
4. Execute and present results

**User:** "How many orders were placed last month?"
**Process:**
1. Search for "order" and date-related columns
2. Find ORDERS table with ORDER_DATE column
3. Generate: SELECT COUNT(*) FROM ORDERS WHERE ORDER_DATE >= ADD_MONTHS(SYSDATE, -1)
4. Execute and present count

Remember: Always use the tools systematically and provide clear, accurate results with proper explanations.
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
                state_modifier=system_prompt,
                checkpointer=self.memory
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
            
            # Get the last user message as the main query
            user_query = ""
            for msg in reversed(messages):
                if msg.role == "user":
                    user_query = msg.content
                    break
            
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
                    if data.get("success") and "results" in data:
                        return QueryResult(
                            query=data.get("query", ""),
                            results=data.get("results", []),
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