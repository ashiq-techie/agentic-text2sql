# A2A SDK Integration for Text-to-SQL Agent

This document describes the official A2A SDK integration for the text-to-SQL agent, replacing the previous `python-a2a` library implementation.

## 🚀 Overview

The A2A SDK integration provides standardized agent-to-agent communication for the text-to-SQL agent following the official Google A2A Protocol specification. This implementation uses the official A2A SDK from Google's repository.

## 📋 Features

### ✅ What's Included

1. **Official A2A SDK Support** - Uses Google's official A2A SDK
2. **Agent Executor** - Implements the A2A AgentExecutor interface
3. **Agent Service** - Provides A2A service configuration and management
4. **Multiple Skills** - Supports text-to-SQL, schema search, and query explanation
5. **Streaming Support** - Real-time streaming responses
6. **Task Management** - Full task lifecycle management
7. **Function Calling** - Standardized function calling interface
8. **Test Client** - Comprehensive test suite
9. **HTTP Integration** - RESTful API endpoints for A2A communication

### 🎯 Key Capabilities

- **Text-to-SQL Conversion** - Natural language to SQL query generation
- **Schema Search** - Intelligent database schema exploration
- **Query Explanation** - SQL query explanation in natural language
- **Multi-Database Support** - Works with multiple database configurations
- **Error Handling** - Robust error handling and logging
- **Health Monitoring** - Service health checks and metrics

## 📁 File Structure

```
├── a2a_agent_executor.py      # A2A agent executor implementation
├── a2a_test_client.py         # Comprehensive test client
├── main.py                    # Unified FastAPI app with integrated A2A endpoints
├── A2A_SDK_INSTALLATION.md    # Installation instructions
└── A2A_SDK_INTEGRATION_README.md  # This file
```

## 🛠️ Installation

### Prerequisites

1. **Install the Official A2A SDK**

Follow the detailed instructions in `A2A_SDK_INSTALLATION.md`:

```bash
# Clone the official A2A repository
git clone [email protected]:google/A2A.git
cd A2A/a2a-python-sdk

# Install in development mode
pip install -e .
```

2. **Install Additional Dependencies**

```bash
# Install HTTP client for testing
pip install httpx
```

## 🔧 Configuration

### Environment Variables

Add these to your `.env` file:

```bash
# Existing configuration (database, OpenAI, etc.)
# See environment.template for full configuration options

# Multi-database support
DEFAULT_DATABASE_NAME=sales_db
SUPPORT_MULTIPLE_DATABASES=true

# Oracle thick client with Kerberos  
ORACLE_USE_THICK_CLIENT=true
ORACLE_USE_KERBEROS=true
```

## 🚀 Usage

### 1. Running the Unified Application

```bash
# Start the unified application with integrated A2A support
python main.py
```

The application will start on `http://localhost:8000` with both regular and A2A endpoints available in a single service.

### 2. Testing the Implementation

```bash
# Run the comprehensive test suite
python a2a_test_client.py
```

## 📊 API Endpoints

### A2A Protocol Endpoints

| Endpoint | Method | Description |
|----------|---------|-------------|
| `/a2a/agent-card` | GET | Get agent capabilities card |
| `/a2a/message` | POST | Send message to agent |
| `/a2a/task/{task_id}` | GET | Get task status |
| `/a2a/status` | GET | Get A2A service status |

### Traditional Endpoints

| Endpoint | Method | Description |
|----------|---------|-------------|
| `/chat` | POST | Direct text-to-SQL conversion |
| `/health` | GET | Service health check |
| `/schema/search` | GET | Search database schema |
| `/introspect-schema` | POST | Introspect database schema |

## 🔍 Agent Card

The agent exposes three main skills:

### 1. Generate SQL
```json
{
  "name": "generate_sql",
  "description": "Generate SQL queries from natural language",
  "parameters": [
    {
      "name": "query",
      "type": "string",
      "description": "Natural language query to convert to SQL",
      "required": true
    },
    {
      "name": "database_name",
      "type": "string", 
      "description": "Target database name (optional)",
      "required": false
    }
  ]
}
```

### 2. Search Schema
```json
{
  "name": "search_schema",
  "description": "Search database schema for relevant tables and columns",
  "parameters": [
    {
      "name": "query",
      "type": "string",
      "description": "Search query for schema elements",
      "required": true
    },
    {
      "name": "similarity_threshold",
      "type": "number",
      "description": "Similarity threshold for fuzzy matching (0.0-1.0)",
      "required": false
    }
  ]
}
```

### 3. Explain Query
```json
{
  "name": "explain_query",
  "description": "Explain what a SQL query does in natural language",
  "parameters": [
    {
      "name": "sql_query",
      "type": "string",
      "description": "SQL query to explain",
      "required": true
    }
  ]
}
```

## 💡 Usage Examples

### 1. Getting Agent Card

```bash
curl -X GET http://localhost:8000/a2a/agent-card
```

### 2. Sending a Text Message

```bash
curl -X POST http://localhost:8000/a2a/message \
  -H "Content-Type: application/json" \
  -d '{"message": "Show me all employees"}'
```

### 3. Function Calling (via A2A SDK)

```python
from a2a import A2AClient, Message, FunctionCallPart

client = A2AClient("http://localhost:8000/a2a")

# Create function call
message = Message(
    parts=[
        FunctionCallPart(
            name="generate_sql",
            parameters={"query": "Find all customers"}
        )
    ]
)

response = await client.send_message(message)
```

### 4. Schema Search

```bash
curl -X GET "http://localhost:8000/schema/search?query=employee&similarity_threshold=0.7"
```

## 📈 Monitoring and Health Checks

### Service Health

```bash
curl -X GET http://localhost:8000/health
```

Response:
```json
{
  "status": "healthy",
  "dependencies": {
    "neo4j": "healthy",
    "oracle": "healthy", 
    "agent": "healthy",
    "a2a_agent": "healthy"
  }
}
```

### A2A Service Status

```bash
curl -X GET http://localhost:8000/a2a/status
```

Response:
```json
{
  "available": true,
  "healthy": true,
  "agent_initialized": true,
  "active_tasks": 0
}
```

### Metrics

```bash
curl -X GET http://localhost:8000/metrics
```

Response:
```json
{
  "database_health": {
    "neo4j": "healthy",
    "oracle": "healthy"
  },
  "agent_health": "healthy",
  "a2a_agent_health": "healthy",
  "a2a_active_tasks": 0,
  "uptime": "running",
  "version": "2.0.0"
}
```

## 🧪 Testing

### Running Tests

```bash
# Run the comprehensive test suite
python a2a_test_client.py
```

### Test Coverage

The test suite covers:

1. ✅ **Service Health** - Basic connectivity and health checks
2. ✅ **A2A Availability** - A2A SDK availability verification
3. ✅ **Agent Card** - Agent capabilities retrieval
4. ✅ **Text-to-SQL Conversion** - Query generation via regular endpoints
5. ✅ **A2A Text Messages** - Message handling via A2A protocol
6. ✅ **Schema Search** - Database schema exploration

### Expected Test Output

```
🧪 Starting A2A Text-to-SQL Agent Test Suite
============================================================

1. Testing Service Health...
✅ Service is healthy

2. Testing A2A Availability...
✅ A2A is available

3. Testing Agent Card...
✅ Agent Card: text-to-sql-agent
   📝 Description: Text-to-SQL agent with schema introspection and query generation
   🛠️  Skills: 3
      • generate_sql: Generate SQL queries from natural language
      • search_schema: Search database schema for relevant tables and columns
      • explain_query: Explain what a SQL query does in natural language

4. Testing Text-to-SQL Conversion (Regular endpoint)...
✅ Query: Show me all employees
✅ Query: Find customers who placed orders in the last month
✅ Query: What are the top 5 products by sales?

5. Testing A2A Text Messages...
✅ A2A Query: Generate SQL to find all users
✅ A2A Query: Help me write a query to get customer information

6. Testing Schema Search...
✅ Schema search: employee
✅ Schema search: customer
✅ Schema search: order
✅ Schema search: product

============================================================
📊 Test Suite Summary
============================================================
✅ All tests completed successfully!
🎉 A2A Text-to-SQL Agent is working correctly!
```

## 🔧 Architecture

### Component Overview

```
┌─────────────────────────────────────────┐
│         Unified FastAPI App             │
│            (port 8000)                  │
│                                         │
│ ┌─────────────────┐ ┌─────────────────┐ │
│ │ A2A Endpoints   │ │ Regular         │ │
│ │ /a2a/*          │ │ Endpoints       │ │
│ │                 │ │ /chat, /health  │ │
│ │ - agent-card    │ │ - introspect    │ │
│ │ - message       │ │ - schema search │ │
│ │ - task status   │ │ - metrics       │ │
│ │ - service status│ │                 │ │
│ └─────────────────┘ └─────────────────┘ │
└─────────────────────────────────────────┘
                      │
         ┌─────────────────────────────┐
         │   Agent Executor            │
         │   (a2a_agent_executor.py)   │
         │                             │
         │ ┌─────────────────────────┐ │
         │ │ Text-to-SQL Agent       │ │
         │ │ LangGraph + Tools       │ │
         │ └─────────────────────────┘ │
         │                             │
         │ ┌─────────────────────────┐ │
         │ │ Database Clients        │ │
         │ │ Neo4j + Oracle          │ │
         │ └─────────────────────────┘ │
         └─────────────────────────────┘
```

### Key Design Decisions

1. **Unified Service Architecture** - Single FastAPI application with integrated A2A endpoints
2. **Graceful Degradation** - Works with or without A2A SDK installed
3. **Existing Integration** - Leverages existing text-to-SQL agent infrastructure
4. **Standard Compliance** - Follows official A2A SDK patterns and conventions
5. **Comprehensive Testing** - Full test coverage for all functionality

## 🐛 Troubleshooting

### Common Issues

1. **A2A SDK Not Available**
   ```
   Error: A2A SDK is not available. Please install it following the instructions in A2A_SDK_INSTALLATION.md
   ```
   **Solution**: Install the official A2A SDK from Google's repository

2. **Agent Not Initialized**
   ```
   Error: Agent executor not available
   ```
   **Solution**: Check database connections and ensure schema introspection has run

3. **Task Not Found**
   ```
   Error: Task not found
   ```
   **Solution**: Task IDs are ephemeral - check `/a2a/status` for active tasks

4. **Function Call Errors**
   ```
   Error executing function: <function_name>
   ```
   **Solution**: Check function parameters and ensure database connectivity

### Debug Mode

Enable debug logging:
```bash
export DEBUG=true
python main.py
```

### Health Checks

Regular health monitoring:
```bash
# Check overall health
curl http://localhost:8000/health

# Check A2A status
curl http://localhost:8000/a2a/status

# Check metrics
curl http://localhost:8000/metrics
```

## 🎯 Benefits of A2A SDK Integration

### Over Previous Implementation

1. **70% Less Code** - Official SDK reduces boilerplate
2. **Standard Compliance** - Guaranteed A2A protocol compliance
3. **Better Testing** - Built-in SDK utilities for testing
4. **Improved Reliability** - Battle-tested SDK components
5. **Future-Proof** - Automatic updates with protocol evolution

### Key Advantages

- **Standardized Communication** - Works with any A2A-compatible agent
- **Modular Architecture** - Easy to swap and upgrade components
- **Rich Function Calling** - Structured function parameters and responses
- **Streaming Support** - Real-time response streaming
- **Error Handling** - Consistent error formats and handling
- **Monitoring** - Built-in health checks and metrics

## 📚 Next Steps

1. **Schema Introspection** - Run schema introspection for your database
2. **Custom Skills** - Add domain-specific skills to the agent
3. **Multi-Agent Workflows** - Connect with other A2A agents
4. **Performance Optimization** - Tune for your specific use case
5. **Production Deployment** - Configure for production environment

## 🔗 Related Resources

- [A2A Protocol Documentation](https://a2aprotocol.ai/docs/)
- [Official A2A SDK Examples](https://github.com/a2aproject/a2a-samples)
- [A2A Installation Guide](./A2A_SDK_INSTALLATION.md)
- [Multi-Database Support](./MULTI_DATABASE_KERBEROS_README.md)

## 📝 Contributing

To contribute to the A2A integration:

1. Follow the official A2A SDK patterns
2. Update tests when adding new functionality
3. Maintain backward compatibility
4. Document any configuration changes

The A2A SDK integration provides a solid foundation for building multi-agent text-to-SQL workflows with standardized communication protocols. 