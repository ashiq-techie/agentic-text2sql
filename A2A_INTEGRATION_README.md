# A2A Protocol Integration

## Overview

This document describes the **Agent2Agent (A2A) protocol** integration for our text-to-SQL agent. The A2A protocol enables standardized communication between AI agents, allowing them to discover capabilities, exchange tasks, and collaborate on complex workflows.

## What is A2A?

The Agent2Agent protocol is an open standard initiated by Google that provides:

- **Standardized Communication**: Common message formats and interaction patterns
- **Agent Discovery**: Agent cards describing capabilities and metadata
- **Task Management**: Lifecycle management for long-running operations
- **Rich Content Support**: Text, structured data, files, and multimedia
- **Streaming Support**: Real-time progress updates via Server-Sent Events

## Implementation Architecture

### Core Components

1. **A2A Schemas** (`a2a_schemas.py`)
   - Complete Pydantic models for A2A protocol
   - Message types, task lifecycle, agent cards
   - Utility functions for creating common structures

2. **Agent Card** (`agent_card.py`)
   - Describes our text-to-SQL agent capabilities
   - Advertises supported operations and limitations
   - Includes metadata and examples

3. **Task Manager** (`a2a_task_manager.py`)
   - Manages A2A task lifecycle
   - Integrates with existing LangGraph agent
   - Supports both sync and streaming execution

4. **Message Handler** (`a2a_message_handler.py`)
   - Converts between A2A and internal message formats
   - Validates message structure
   - Handles different content types

5. **API Endpoints** (in `main.py`)
   - `/agent-card` - Get agent capabilities
   - `/tasks/send` - Send synchronous tasks
   - `/tasks/{task_id}` - Get task status/results
   - `/tasks/sendSubscribe` - Send streaming tasks

## Agent Card

Our agent advertises the following capabilities:

### Core Capabilities

1. **Text-to-SQL Conversion**
   - Convert natural language to SQL queries
   - Support for Oracle and Neo4j databases
   - Schema-aware query generation

2. **Schema Exploration**
   - Search database schemas with fuzzy matching
   - Discover tables, columns, and relationships
   - Infer foreign key relationships

3. **Query Execution**
   - Safe execution of read-only queries
   - Result formatting and validation
   - Error handling and timeout management

4. **Database Introspection**
   - Analyze database schemas
   - Build knowledge graph representations
   - Extract metadata and relationships

### Agent Metadata

- **ID**: `text-to-sql-agent`
- **Version**: `1.0.0`
- **Streaming**: ✅ Supported
- **Max Concurrent Tasks**: 5
- **Supported Formats**: text, json, sql

## API Endpoints

### GET /agent-card

Returns the agent card describing capabilities.

**Response:**
```json
{
  "id": "text-to-sql-agent",
  "name": "Text-to-SQL Agent",
  "description": "An advanced text-to-SQL conversion agent...",
  "version": "1.0.0",
  "capabilities": [...],
  "streaming": true,
  "max_concurrent_tasks": 5
}
```

### POST /tasks/send

Send a task for synchronous execution.

**Request:**
```json
{
  "input": {
    "messages": [
      {
        "role": "user",
        "parts": [
          {
            "type": "text",
            "text": "Show me all customers from New York"
          }
        ]
      }
    ]
  },
  "metadata": {}
}
```

**Response:**
```json
{
  "task_id": "uuid",
  "status": "completed"
}
```

### GET /tasks/{task_id}

Get task status and results.

**Response:**
```json
{
  "task": {
    "id": "uuid",
    "state": {
      "status": "completed",
      "progress": 1.0,
      "status_message": "Task completed successfully"
    },
    "output": {
      "messages": [...],
      "artefacts": [...]
    }
  }
}
```

### POST /tasks/sendSubscribe

Send a task with streaming updates via Server-Sent Events.

**Request:** Same as `/tasks/send`

**Response:** Stream of events:
```
event: task_progress
data: {"task_id": "uuid", "progress": 0.1, "status_message": "Understanding query..."}

event: task_progress
data: {"task_id": "uuid", "progress": 0.5, "status_message": "Generating SQL..."}

event: task_complete
data: {"task_id": "uuid", "output": {...}}
```

## Message Format

### A2A Message Structure

```json
{
  "id": "uuid",
  "role": "user|assistant|system",
  "parts": [
    {
      "type": "text",
      "text": "Show me all customers"
    },
    {
      "type": "data",
      "data": {"query_type": "customer_lookup"},
      "schema_name": "query_metadata"
    }
  ],
  "timestamp": "2024-01-15T10:30:00Z",
  "metadata": {}
}
```

### Content Types

- **TextPart**: Plain text content
- **DataPart**: Structured JSON data
- **FilePart**: Base64-encoded file content
- **ImagePart**: Base64-encoded image data

### Artefacts

Results are packaged as artefacts:

```json
{
  "id": "uuid",
  "title": "Generated SQL Query",
  "description": "SQL query for customer lookup",
  "parts": [
    {
      "type": "text",
      "text": "SELECT * FROM customers WHERE city = 'New York'"
    },
    {
      "type": "data",
      "data": {
        "query": "SELECT * FROM customers WHERE city = 'New York'",
        "database": "Oracle",
        "type": "sql"
      }
    }
  ],
  "metadata": {
    "query_type": "sql",
    "generated_at": "2024-01-15T10:30:00Z"
  }
}
```

## Task Lifecycle

### Task States

- **created**: Task has been created
- **in_progress**: Task is being executed
- **completed**: Task finished successfully
- **failed**: Task encountered an error
- **cancelled**: Task was cancelled
- **input_required**: Task needs additional input

### Streaming Events

- **task_progress**: Progress update with status message
- **task_complete**: Task finished with results
- **task_error**: Task failed with error details

## Integration Examples

### Basic Query

```python
from a2a_schemas import TaskInput, TaskSendRequest, create_user_message

# Create task
user_message = create_user_message("Show me all products")
task_request = TaskSendRequest(
    input=TaskInput(messages=[user_message])
)

# Send to agent
response = await client.post("/tasks/send", json=task_request.dict())
```

### Streaming Query

```python
from a2a_schemas import TaskSubscribeRequest

# Create streaming task
task_request = TaskSubscribeRequest(
    input=TaskInput(messages=[user_message])
)

# Listen for events
async for event in client.stream_events("/tasks/sendSubscribe", task_request):
    print(f"Progress: {event['data']['progress']}")
    if event['event'] == 'task_complete':
        results = event['data']['output']
        break
```

## Testing

Use the provided test script to validate the A2A integration:

```bash
# Run A2A protocol tests
python test_a2a_api.py
```

The test suite covers:
- Agent card retrieval
- Simple task execution
- SQL query generation
- Streaming task execution
- Schema exploration
- Error handling

## Configuration

The A2A integration uses existing configuration from `config.py`:

```python
# A2A-specific settings
ENABLE_A2A_PROTOCOL = True
A2A_MAX_CONCURRENT_TASKS = 5
A2A_TASK_TIMEOUT = 300  # seconds
A2A_STREAMING_ENABLED = True
```

## Benefits

### For Agent Developers

1. **Standardized Interface**: Common API patterns across agents
2. **Rich Content Support**: Handle text, data, files seamlessly
3. **Streaming Capabilities**: Real-time progress updates
4. **Error Handling**: Consistent error reporting

### For Multi-Agent Systems

1. **Agent Discovery**: Automatic capability detection
2. **Task Delegation**: Route tasks to appropriate agents
3. **Composition**: Chain multiple agents together
4. **Interoperability**: Mix agents from different frameworks

### For Users

1. **Consistent Experience**: Same interaction patterns
2. **Progress Visibility**: Real-time task updates
3. **Rich Results**: Structured data and artefacts
4. **Error Transparency**: Clear error messages

## Limitations

1. **Read-Only Operations**: No DDL or data modification
2. **Language Support**: English queries only
3. **Database Dependencies**: Requires configured connections
4. **Concurrent Tasks**: Limited to 5 simultaneous tasks

## Future Enhancements

1. **Multi-Language Support**: Support for multiple languages
2. **Advanced Streaming**: Partial result streaming
3. **Task Chaining**: Link multiple tasks together
4. **Caching**: Cache frequent schema queries
5. **Metrics**: Detailed performance tracking

## References

- [A2A Specification](https://github.com/a2aproject/A2A/blob/main/specification/json/a2a.json)
- [A2A Samples](https://github.com/a2aproject/a2a-samples)
- [A2A Tutorial](https://medium.com/google-cloud/getting-started-with-google-a2a-a-hands-on-tutorial-for-the-agent2agent-protocol-3d3b5e055127)
- [LangGraph A2A Integration](https://github.com/a2aproject/a2a-samples/tree/main/samples/python/agents/langgraph)

## Contributing

When extending the A2A integration:

1. Follow the official A2A specification
2. Add comprehensive tests for new features
3. Update the agent card for new capabilities
4. Maintain backward compatibility
5. Document all changes

## Support

For A2A protocol questions:
- Check the [official A2A repository](https://github.com/a2aproject/A2A)
- Join the A2A community discussions
- Review the specification and samples

For implementation questions:
- Check the test suite for examples
- Review the task manager implementation
- Examine the message handler utilities 