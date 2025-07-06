# Advanced Text-to-SQL Agent

A next-generation text-to-SQL agent that uses Neo4j knowledge graphs and LangGraph for accurate SQL query generation from natural language.

## 🚀 Key Features

- **Knowledge Graph Schema Storage**: Oracle database schema stored in Neo4j with relationships
- **Fuzzy Schema Matching**: Handles abbreviated table names (e.g., "Lifecycle" → "LFC")
- **LangGraph React Agent**: Sophisticated reasoning with tool-calling capabilities
- **Async Architecture**: Optimized for low latency and high concurrency
- **Comprehensive API**: RESTful endpoints for chat, schema management, and health checks
- **Modular Design**: Clean, maintainable codebase with proper separation of concerns

## 🏗️ Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   FastAPI App   │    │  LangGraph      │    │   Neo4j         │
│   (main.py)     │───▶│  React Agent    │───▶│  Knowledge      │
│                 │    │  (agent.py)     │    │  Graph          │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Chat UI       │    │  Agent Tools    │    │   Oracle        │
│   (External)    │    │  (agent_tools)  │    │   Database      │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

## 🔧 Components

### Core Components

1. **`main.py`**: FastAPI application with chat endpoint and schema management
2. **`agent.py`**: LangGraph React agent with comprehensive system prompts
3. **`agent_tools.py`**: Tools for Neo4j queries, Oracle queries, and schema search
4. **`schema_introspection.py`**: Oracle schema analysis and Neo4j storage
5. **`clients.py`**: Async database clients for Neo4j and Oracle
6. **`schemas.py`**: Pydantic models for API requests and responses
7. **`config.py`**: Configuration management with environment variables

### Knowledge Graph Structure

The system stores Oracle database schema in Neo4j with the following structure:

```
Database (root)
├── HAS_TABLE → Table Nodes
    ├── HAS_COLUMN → Column Nodes
    └── HAS_FOREIGN_KEY → Other Column Nodes (explicit + inferred)
```

**Node Types:**
- **Database**: Root node representing the Oracle database
- **Table**: Individual tables with metadata (schema, row count, comments)
- **Column**: Table columns with data types, constraints, and properties

**Relationship Types:**
- **HAS_TABLE**: Database → Table
- **HAS_COLUMN**: Table → Column
- **HAS_FOREIGN_KEY**: Column → Column (foreign key relationships)
  - **Explicit**: From Oracle constraint tables
  - **Inferred**: From naming conventions (e.g., `ID_LFC` → `LIFECYCLE.ID`)

### 🔍 Foreign Key Inference

The system automatically infers foreign key relationships from naming conventions:

**Supported Patterns (case-insensitive):**
- `{TABLE}_ID` → Points to `TABLE.ID`
- `ID_{TABLE}` → Points to `TABLE.ID`
- `{TABLE}_KEY` → Points to `TABLE` primary key
- `{TABLE}_FK` → Points to `TABLE` primary key
- Mixed case: `Id_Lfc` → `LifeCycle.Id`
- Abbreviations: `LFC_ID` → `LIFECYCLE.ID`

**Features:**
- **Case-insensitive matching**: Handles mixed case table/column names
- **Fuzzy matching**: For abbreviated table names
- **Configurable similarity thresholds**
- **Confidence scoring**: For inferred relationships
- **Avoids duplicating**: Explicit constraints

## 🛠️ Installation

### Prerequisites

- Python 3.8+
- Neo4j 5.0+
- Oracle Database 19c+
- OpenAI API Key

### Setup

1. **Clone the repository**:
```bash
git clone <repository-url>
cd agentic-text2sql
```

2. **Install dependencies**:
```bash
pip install -r requirements.txt
```

3. **Configure environment variables**:
```bash
cp environment.template .env
# Edit .env with your actual configuration
```

4. **Start Neo4j database**:
```bash
# Using Docker
docker run -d \
  --name neo4j \
  -p 7474:7474 -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/password \
  neo4j:5.15
```

5. **Initialize schema** (one-time setup):
```bash
# Start the application first
python main.py

# Then in another terminal, introspect your Oracle schema
curl -X POST "http://localhost:8000/introspect-schema?schema_name=YOUR_SCHEMA"
```

## 🚀 Usage

### Starting the Application

```bash
python main.py
```

The API will be available at `http://localhost:8000`

### API Endpoints

#### Chat Endpoint
```bash
POST /chat
```

**Request:**
```json
{
  "messages": [
    {
      "role": "user",
      "content": "Show me all active users from the last month"
    }
  ],
  "session_id": "optional-session-id"
}
```

**Response:**
```json
{
  "response": {
    "message": "Here are the active users from the last month...",
    "query_results": {
      "query": "SELECT * FROM USERS WHERE STATUS = 'ACTIVE' AND CREATED_DATE >= ADD_MONTHS(SYSDATE, -1)",
      "results": [...],
      "execution_time": 0.245,
      "row_count": 156
    },
    "execution_time": 2.1,
    "session_id": "optional-session-id"
  },
  "status": "success"
}
```

#### Schema Management

**Introspect Schema:**
```bash
POST /introspect-schema?schema_name=YOUR_SCHEMA
```

**Search Schema:**
```bash
GET /schema/search?query=user%20profile&similarity_threshold=0.6
```

**Get Schema Context:**
```bash
GET /schema/context?table_names=USERS,USER_PROFILES
```

**Get Inferred Relationships:**
```bash
GET /schema/inferred-relationships
```

#### Health Check
```bash
GET /health
```

## 🔄 Workflow

The agent follows a systematic 5-step process:

1. **Understand Query**: Parse natural language and identify requirements
2. **Find Schema**: Use fuzzy matching to find relevant tables/columns
3. **Analyze Context**: Get complete schema information including relationships
4. **Generate SQL**: Create accurate Oracle SQL with proper syntax
5. **Execute & Validate**: Run query and present results with explanations

## 🎯 Example Queries

### Basic Queries
- "Show me all users"
- "How many orders were placed today?"
- "Find active customers in California"

### Complex Queries
- "Show user lifecycle stages with counts"
- "Find top 10 customers by order value this year"
- "List users who haven't logged in for 30 days"

### Fuzzy Matching Examples
- "LFC data" → Finds `LIFECYCLE` or `LifeCycle` tables
- "usr info" → Finds `USER_INFORMATION` or `User_Information` tables
- "ord status" → Finds `ORDER_STATUS` or `Order_Status` columns
- Mixed case: `Id_Usr` → Matches `USER_PROFILES.Id_Usr` → `Users.Id`

## 🔧 Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `NEO4J_URI` | Neo4j connection URI | `bolt://localhost:7687` |
| `NEO4J_USERNAME` | Neo4j username | `neo4j` |
| `NEO4J_PASSWORD` | Neo4j password | `password` |
| `ORACLE_DSN` | Oracle database DSN | `localhost:1521/xe` |
| `ORACLE_USERNAME` | Oracle username | `system` |
| `ORACLE_PASSWORD` | Oracle password | `oracle` |
| `OPENAI_API_KEY` | OpenAI API key | (required) |
| `OPENAI_MODEL` | OpenAI model | `gpt-4-turbo-preview` |
| `API_HOST` | API host | `0.0.0.0` |
| `API_PORT` | API port | `8000` |
| `ENABLE_FK_INFERENCE` | Enable foreign key inference | `true` |
| `FK_INFERENCE_SIMILARITY_THRESHOLD` | Similarity threshold for FK inference | `0.7` |

### Performance Tuning

- **Neo4j**: Configure appropriate memory settings for your schema size
- **Oracle**: Ensure proper indexing on frequently queried columns
- **Connection Pools**: Adjust pool sizes based on expected load
- **Query Limits**: Configure `MAX_RESULTS_LIMIT` appropriately

## 📊 Monitoring

### Health Checks
- `/health` - Overall system health
- `/metrics` - Application metrics

### Logging
The application provides structured logging for:
- Query processing times
- Database connection health
- Agent tool executions
- Error conditions

## 🛡️ Security

### Recommendations
- Use environment variables for sensitive configuration
- Implement proper authentication for production
- Configure CORS appropriately
- Use parameterized queries (automatically handled)
- Regularly update dependencies

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## 📝 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🆘 Troubleshooting

### Common Issues

1. **Connection Errors**: Check database connectivity and credentials
2. **Schema Not Found**: Ensure schema introspection has been run
3. **Agent Errors**: Verify OpenAI API key and model availability
4. **Performance Issues**: Check query complexity and result limits

### Debug Mode
Enable debug mode by setting `DEBUG=true` in your environment variables.

## 📞 Support

For support, please open an issue in the GitHub repository or contact the development team.

---

Built with ❤️ using FastAPI, LangGraph, Neo4j, and OpenAI 