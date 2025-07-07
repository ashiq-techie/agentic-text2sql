"""
Agent Card using Python A2A SDK

Defines the capabilities and metadata for our text-to-SQL agent
using the official Python A2A SDK patterns.
"""
from typing import Dict, Any, List


def get_agent_capabilities() -> Dict[str, Any]:
    """
    Get the agent card for our text-to-SQL agent using A2A SDK format.
    
    This describes what our agent can do and how other agents/systems
    can interact with it via the A2A protocol.
    """
    return {
        "agent_id": "text-to-sql-agent",
        "name": "Text-to-SQL Agent",
        "description": "An advanced text-to-SQL conversion agent that understands database schemas and generates accurate SQL queries from natural language. Features schema-aware query generation, fuzzy matching for table/column names, and intelligent foreign key inference.",
        "version": "2.0.0",  # Updated version using SDK
        "author": "Agentic Text-to-SQL System",
        "created_date": "2024-01-15",
        
        # Supported message types
        "supported_content_types": [
            "text",           # Natural language queries
            "function_call"   # Structured function calls
        ],
        
        # Available functions that other agents can call
        "functions": [
            {
                "name": "generate_sql",
                "description": "Generate SQL query from natural language without executing it",
                "parameters": {
                    "query": {
                        "type": "string",
                        "description": "Natural language query to convert to SQL",
                        "required": True
                    }
                },
                "returns": {
                    "sql_query": "string",
                    "query_type": "string",
                    "generated_at": "string"
                }
            },
            {
                "name": "search_schema",
                "description": "Search database schema for tables and columns",
                "parameters": {
                    "search_term": {
                        "type": "string", 
                        "description": "Term to search for in schema",
                        "required": True
                    },
                    "similarity_threshold": {
                        "type": "number",
                        "description": "Similarity threshold for fuzzy matching (0.0-1.0)",
                        "required": False,
                        "default": 0.6
                    }
                },
                "returns": {
                    "search_term": "string",
                    "results": "array",
                    "count": "number"
                }
            }
        ],
        
        # Core capabilities
        "capabilities": [
            {
                "name": "Text-to-SQL Conversion",
                "description": "Convert natural language queries to SQL statements using database schema knowledge",
                "features": [
                    "Natural language to SQL conversion",
                    "Schema-aware query generation", 
                    "Fuzzy table/column name matching",
                    "Foreign key inference",
                    "Query validation and execution",
                    "Results formatting"
                ]
            },
            {
                "name": "Schema Exploration", 
                "description": "Explore and search database schema information",
                "features": [
                    "Schema search with fuzzy matching",
                    "Table and column discovery",
                    "Relationship mapping",
                    "Foreign key detection",
                    "Metadata extraction"
                ]
            },
            {
                "name": "Query Execution",
                "description": "Execute SQL queries against Oracle and Neo4j databases",
                "features": [
                    "Safe query execution",
                    "Result formatting", 
                    "Error handling",
                    "Query validation"
                ]
            },
            {
                "name": "Database Introspection",
                "description": "Analyze database schemas and build knowledge graphs", 
                "features": [
                    "Schema analysis",
                    "Knowledge graph construction",
                    "Relationship inference",
                    "Metadata extraction"
                ]
            }
        ],
        
        # Technical specifications
        "supported_databases": ["Oracle", "Neo4j"],
        "supported_languages": ["en"],
        "output_formats": ["text", "json", "sql"],
        
        # Operational limits
        "max_concurrent_requests": 5,
        "supports_streaming": True,
        "supports_conversation": True,
        "supports_function_calls": True,
        
        # Example interactions
        "examples": [
            {
                "input": {
                    "type": "text",
                    "content": "Show me all customers from New York"
                },
                "output": {
                    "type": "text", 
                    "content": "SELECT * FROM customers WHERE city = 'New York'"
                }
            },
            {
                "input": {
                    "type": "function_call",
                    "function": "generate_sql",
                    "parameters": {
                        "query": "Find total revenue by product category"
                    }
                },
                "output": {
                    "type": "function_response",
                    "result": {
                        "sql_query": "SELECT category, SUM(revenue) as total_revenue FROM products GROUP BY category",
                        "query_type": "Oracle",
                        "generated_at": "2024-01-15T10:30:00Z"
                    }
                }
            },
            {
                "input": {
                    "type": "text",
                    "content": "What tables are available for customer data?"
                },
                "output": {
                    "type": "text",
                    "content": "I found several customer-related tables: CUSTOMERS, CUSTOMER_ORDERS, CUSTOMER_PROFILES..."
                }
            }
        ],
        
        # Performance and limitations
        "performance": {
            "avg_response_time": "< 2 seconds",
            "concurrent_requests": "Up to 5",
            "supported_query_complexity": "High"
        },
        
        "limitations": [
            "Read-only database access",
            "English language queries only", 
            "Requires pre-configured database connections",
            "No DDL operations",
            "Query timeout limits apply"
        ],
        
        # Tags for discovery
        "tags": [
            "sql", "database", "nlp", "schema", "query-generation",
            "oracle", "neo4j", "text-to-sql", "langraph", "a2a"
        ],
        
        "use_cases": [
            "Business intelligence queries",
            "Database exploration", 
            "Report generation",
            "Data analysis",
            "Schema documentation",
            "Multi-agent database workflows"
        ]
    }


# Export the agent card
AGENT_CARD_SDK = get_agent_capabilities() 