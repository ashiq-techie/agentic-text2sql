"""
A2A Agent Server using Python A2A SDK

Integrates our text-to-SQL agent with the official Python A2A SDK.
"""
import logging
import asyncio
from typing import Dict, Any, Optional
import json
from datetime import datetime

from python_a2a import (
    A2AServer, Message, TextContent, FunctionCallContent, 
    FunctionResponseContent, MessageRole, run_server, Conversation
)
from agent import create_text_to_sql_agent, invoke_agent, create_agent_session

logger = logging.getLogger(__name__)


class TextToSQLAgent(A2AServer):
    """
    Text-to-SQL Agent using Python A2A SDK.
    
    This agent integrates our existing LangGraph text-to-SQL system
    with the A2A protocol using the official Python SDK.
    """
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._agent = None
        self._agent_session = None
        self._initialized = False
        
    async def initialize(self):
        """Initialize the underlying LangGraph agent."""
        if self._initialized:
            return
            
        try:
            self._agent = await create_text_to_sql_agent()
            self._agent_session = await create_agent_session()
            self._initialized = True
            logger.info("Text-to-SQL agent initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize agent: {e}")
            raise
    
    def handle_message(self, message: Message) -> Message:
        """
        Handle incoming A2A messages.
        
        Args:
            message: A2A message from client
            
        Returns:
            A2A response message
        """
        if not self._initialized:
            # Run initialization synchronously in the event loop
            asyncio.create_task(self.initialize())
            return Message(
                content=TextContent(
                    text="Agent is initializing, please try again in a moment."
                ),
                role=MessageRole.AGENT,
                parent_message_id=message.message_id,
                conversation_id=message.conversation_id
            )
        
        if message.content.type == "text":
            return self._handle_text_message(message)
        elif message.content.type == "function_call":
            return self._handle_function_call(message)
        else:
            return Message(
                content=TextContent(
                    text="I can only handle text messages and function calls at the moment."
                ),
                role=MessageRole.AGENT,
                parent_message_id=message.message_id,
                conversation_id=message.conversation_id
            )
    
    def _handle_text_message(self, message: Message) -> Message:
        """Handle text-based queries."""
        try:
            user_query = message.content.text
            logger.info(f"Processing text query: {user_query}")
            
            # Convert to agent format
            agent_messages = [("user", user_query)]
            
            # Execute agent (this needs to be async, but A2AServer expects sync)
            # We'll need to run this in the event loop
            loop = asyncio.get_event_loop()
            result = loop.run_until_complete(
                invoke_agent(
                    self._agent,
                    {"messages": agent_messages},
                    session=self._agent_session
                )
            )
            
            # Extract response
            if result and "messages" in result:
                agent_response = result["messages"][-1][1] if result["messages"] else "No response generated"
            else:
                agent_response = "Unable to process your query at the moment."
            
            # Create structured response if we have SQL
            response_text = agent_response
            if "sql_query" in result:
                sql_query = result["sql_query"]
                response_text += f"\n\nGenerated SQL:\n```sql\n{sql_query}\n```"
                
                if "results" in result:
                    results = result["results"]
                    if results:
                        response_text += f"\n\nQuery returned {len(results)} rows."
                    else:
                        response_text += "\n\nQuery executed successfully (no results)."
            
            return Message(
                content=TextContent(text=response_text),
                role=MessageRole.AGENT,
                parent_message_id=message.message_id,
                conversation_id=message.conversation_id
            )
            
        except Exception as e:
            logger.error(f"Error processing text message: {e}")
            return Message(
                content=TextContent(
                    text=f"I encountered an error processing your request: {str(e)}"
                ),
                role=MessageRole.AGENT,
                parent_message_id=message.message_id,
                conversation_id=message.conversation_id
            )
    
    def _handle_function_call(self, message: Message) -> Message:
        """Handle function calls for specific operations."""
        try:
            function_name = message.content.name
            params = {p.name: p.value for p in message.content.parameters}
            
            logger.info(f"Processing function call: {function_name} with params: {params}")
            
            if function_name == "generate_sql":
                # Function to generate SQL without executing
                query = params.get("query", "")
                
                if not query:
                    raise ValueError("Query parameter is required")
                
                # Process with agent
                loop = asyncio.get_event_loop()
                result = loop.run_until_complete(
                    invoke_agent(
                        self._agent,
                        {"messages": [("user", query)]},
                        session=self._agent_session
                    )
                )
                
                sql_query = result.get("sql_query", "No SQL generated")
                
                return Message(
                    content=FunctionResponseContent(
                        name="generate_sql",
                        response={
                            "sql_query": sql_query,
                            "query_type": result.get("database_type", "unknown"),
                            "generated_at": datetime.utcnow().isoformat()
                        }
                    ),
                    role=MessageRole.AGENT,
                    parent_message_id=message.message_id,
                    conversation_id=message.conversation_id
                )
            
            elif function_name == "search_schema":
                # Function to search database schema
                search_term = params.get("search_term", "")
                similarity_threshold = params.get("similarity_threshold", 0.6)
                
                if not search_term:
                    raise ValueError("Search term is required")
                
                # Use schema search functionality
                from schema_introspection import schema_introspector
                
                loop = asyncio.get_event_loop()
                results = loop.run_until_complete(
                    schema_introspector.find_relevant_schema(search_term, similarity_threshold)
                )
                
                return Message(
                    content=FunctionResponseContent(
                        name="search_schema",
                        response={
                            "search_term": search_term,
                            "results": results,
                            "count": len(results)
                        }
                    ),
                    role=MessageRole.AGENT,
                    parent_message_id=message.message_id,
                    conversation_id=message.conversation_id
                )
            
            else:
                raise ValueError(f"Unknown function: {function_name}")
                
        except Exception as e:
            logger.error(f"Error processing function call: {e}")
            return Message(
                content=FunctionResponseContent(
                    name=message.content.name,
                    response={"error": str(e)}
                ),
                role=MessageRole.AGENT,
                parent_message_id=message.message_id,
                conversation_id=message.conversation_id
            )


# Global agent instance
text_to_sql_agent = TextToSQLAgent()


async def start_a2a_server(host: str = "0.0.0.0", port: int = 5000):
    """Start the A2A server."""
    await text_to_sql_agent.initialize()
    logger.info(f"Starting A2A server on {host}:{port}")
    run_server(text_to_sql_agent, host=host, port=port)


if __name__ == "__main__":
    # Run the A2A server standalone
    asyncio.run(start_a2a_server()) 