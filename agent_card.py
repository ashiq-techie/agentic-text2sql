"""
Agent Card for Text-to-SQL Agent

Defines the capabilities and metadata for our text-to-SQL agent
following the A2A protocol specification.
"""
from a2a_schemas import AgentCard, Capability


def create_text_to_sql_agent_card() -> AgentCard:
    """
    Create the agent card for our text-to-SQL agent.
    
    This describes what our agent can do and how other agents/systems
    can interact with it via the A2A protocol.
    """
    capabilities = [
        Capability(
            name="text_to_sql_conversion",
            description="Convert natural language queries to SQL statements using database schema knowledge",
            input_types=["text"],
            output_types=["text", "data"],
            parameters={
                "supported_databases": ["Oracle", "Neo4j"],
                "features": [
                    "Natural language to SQL conversion",
                    "Schema-aware query generation",
                    "Fuzzy table/column name matching",
                    "Foreign key inference",
                    "Query validation and execution",
                    "Results formatting"
                ],
                "example_queries": [
                    "Show me all customers from the lifecycle table",
                    "Find products with price above 100",
                    "Get customer orders from last month",
                    "List all tables in the database"
                ]
            }
        ),
        Capability(
            name="schema_exploration",
            description="Explore and search database schema information",
            input_types=["text"],
            output_types=["data"],
            parameters={
                "features": [
                    "Schema search with fuzzy matching",
                    "Table and column discovery",
                    "Relationship mapping",
                    "Foreign key detection",
                    "Metadata extraction"
                ],
                "supported_operations": [
                    "Find tables by name pattern",
                    "Get table schema details",
                    "List database relationships",
                    "Search column names",
                    "Get inferred foreign keys"
                ]
            }
        ),
        Capability(
            name="query_execution",
            description="Execute SQL queries against Oracle and Neo4j databases",
            input_types=["text", "data"],
            output_types=["data"],
            parameters={
                "supported_databases": ["Oracle", "Neo4j"],
                "query_types": ["SELECT", "Cypher"],
                "features": [
                    "Safe query execution",
                    "Result formatting",
                    "Error handling",
                    "Query validation"
                ],
                "limitations": [
                    "Read-only queries only",
                    "No DDL operations",
                    "Query timeout limits apply"
                ]
            }
        ),
        Capability(
            name="database_introspection",
            description="Analyze database schemas and build knowledge graphs",
            input_types=["text"],
            output_types=["data"],
            parameters={
                "features": [
                    "Schema analysis",
                    "Knowledge graph construction",
                    "Relationship inference",
                    "Metadata extraction"
                ],
                "supported_operations": [
                    "Full schema introspection",
                    "Incremental schema updates",
                    "Foreign key inference",
                    "Table relationship mapping"
                ]
            }
        )
    ]
    
    return AgentCard(
        id="text-to-sql-agent",
        name="Text-to-SQL Agent",
        description="An advanced text-to-SQL conversion agent that understands database schemas and generates accurate SQL queries from natural language. Features schema-aware query generation, fuzzy matching for table/column names, and intelligent foreign key inference.",
        version="1.0.0",
        capabilities=capabilities,
        streaming=True,  # We support streaming for long-running operations
        max_concurrent_tasks=5,  # Can handle multiple requests concurrently
        supported_formats=["text", "json", "sql"],
        metadata={
            "author": "Agentic Text-to-SQL System",
            "created_date": "2024-01-15",
            "tags": ["sql", "database", "nlp", "schema", "query-generation"],
            "supported_databases": ["Oracle", "Neo4j"],
            "languages": ["en"],
            "categories": ["database", "query-generation", "natural-language-processing"],
            "use_cases": [
                "Business intelligence queries",
                "Database exploration",
                "Report generation",
                "Data analysis",
                "Schema documentation"
            ],
            "examples": [
                {
                    "input": "Show me all customers from New York",
                    "output": "SELECT * FROM customers WHERE city = 'New York'"
                },
                {
                    "input": "Find the total revenue by product category",
                    "output": "SELECT category, SUM(revenue) as total_revenue FROM products GROUP BY category"
                },
                {
                    "input": "List all tables related to orders",
                    "output": "Schema information about order-related tables including relationships"
                }
            ],
            "performance": {
                "avg_response_time": "< 2 seconds",
                "concurrent_requests": "Up to 5",
                "supported_query_complexity": "High"
            },
            "limitations": [
                "Read-only database access",
                "English language queries only",
                "Requires pre-configured database connections"
            ]
        }
    )


# Global agent card instance
AGENT_CARD = create_text_to_sql_agent_card() 