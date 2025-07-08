# Multi-Database Support and Kerberos Authentication

This document describes the enhanced features for supporting multiple databases and Kerberos authentication in the text-to-SQL agent.

## 🚀 New Features

### 1. **Multi-Database Support**
- Support for multiple Oracle databases in a single deployment
- Each database gets its own namespace in Neo4j
- Parameterized schema introspection with database names
- Configurable single vs. multi-database mode

### 2. **Oracle Thick Client with Kerberos**
- Support for Oracle thick client for advanced features
- Kerberos authentication (no username/password required)
- Configurable Oracle client library path
- Automatic detection of authentication method

## 🔧 Configuration

### Environment Variables

```bash
# Database Parameterization
DEFAULT_DATABASE_NAME=oracle_main
SUPPORT_MULTIPLE_DATABASES=true

# Oracle Thick Client Configuration
ORACLE_USE_THICK_CLIENT=true
ORACLE_LIB_DIR=/opt/oracle/instantclient_21_1
ORACLE_USE_KERBEROS=true

# When using Kerberos, username/password are ignored
ORACLE_USERNAME=  # Not used with Kerberos
ORACLE_PASSWORD=  # Not used with Kerberos
```

### Single Database Mode
```bash
SUPPORT_MULTIPLE_DATABASES=false
DEFAULT_DATABASE_NAME=my_oracle_db
```

### Multiple Database Mode
```bash
SUPPORT_MULTIPLE_DATABASES=true
DEFAULT_DATABASE_NAME=primary_db
```

## 📊 Usage Examples

### 1. Schema Introspection for Different Databases

```bash
# Introspect default database
curl -X POST "http://localhost:8000/introspect-schema"

# Introspect specific database
curl -X POST "http://localhost:8000/introspect-schema?database_name=sales_db"

# Introspect specific database and schema
curl -X POST "http://localhost:8000/introspect-schema?database_name=hr_db&schema_name=EMPLOYEES"
```

### 2. Multiple Database Storage in Neo4j

In multi-database mode, each database gets its own namespace:

```cypher
// Database nodes
(:SchemaNode {id: "database_sales_db", type: "database", name: "sales_db"})
(:SchemaNode {id: "database_hr_db", type: "database", name: "hr_db"})

// Table nodes (database-specific)
(:SchemaNode {id: "sales_db_table_ORDERS", type: "table", name: "ORDERS", database: "sales_db"})
(:SchemaNode {id: "hr_db_table_EMPLOYEES", type: "table", name: "EMPLOYEES", database: "hr_db"})

// Column nodes (database-specific)
(:SchemaNode {id: "sales_db_column_ORDERS_ORDER_ID", type: "column", name: "ORDER_ID", database: "sales_db"})
(:SchemaNode {id: "hr_db_column_EMPLOYEES_EMP_ID", type: "column", name: "EMP_ID", database: "hr_db"})
```

### 3. Oracle Thick Client Setup

#### Prerequisites
1. Install Oracle Instant Client
2. Set up Kerberos authentication
3. Configure Oracle client libraries

#### Configuration Steps

1. **Install Oracle Instant Client:**
```bash
# Example for Linux
wget https://download.oracle.com/otn_software/linux/instantclient/instantclient-basic-linux.x64-21.1.0.0.0.zip
unzip instantclient-basic-linux.x64-21.1.0.0.0.zip
export ORACLE_LIB_DIR=/opt/oracle/instantclient_21_1
```

2. **Set Environment Variables:**
```bash
export ORACLE_USE_THICK_CLIENT=true
export ORACLE_LIB_DIR=/opt/oracle/instantclient_21_1
export ORACLE_USE_KERBEROS=true
```

3. **Configure Kerberos (if using):**
```bash
# Ensure Kerberos is configured and you have a valid ticket
kinit your_username@YOUR_REALM
klist  # Verify ticket
```

## 🔍 API Changes

### Enhanced Schema Introspection Endpoint

```python
@app.post("/introspect-schema")
async def introspect_schema_endpoint(
    background_tasks: BackgroundTasks,
    schema_name: str = None,          # Optional: Oracle schema filter
    database_name: str = None         # NEW: Database name parameter
):
```

**Response:**
```json
{
    "message": "Schema introspection started",
    "database_name": "sales_db",
    "schema_name": "SALES",
    "status": "in_progress"
}
```

### Schema Search with Database Context

When searching schema, results now include database context:

```json
{
    "query": "customer orders",
    "results": [
        {
            "table_name": "ORDERS",
            "database": "sales_db",
            "table_score": 0.85,
            "columns": [
                {
                    "name": "CUSTOMER_ID",
                    "database": "sales_db",
                    "score": 0.92
                }
            ]
        }
    ]
}
```

## 🛠️ Advanced Configuration

### Database-Specific Connection Pools

Each database connection maintains its own pool:

```python
# In clients.py
class OracleClient:
    def __init__(self, database_name: str = None):
        self.database_name = database_name or settings.default_database_name
        # ... rest of initialization
```

### Custom Schema Introspection

```python
# Programmatic usage
schema_introspector = SchemaIntrospector()

# Introspect specific database
schema_graph = await schema_introspector.introspect_oracle_schema(
    schema_name="SALES", 
    database_name="sales_db"
)

# Store with database context
await schema_introspector.store_schema_in_neo4j(
    schema_graph, 
    database_name="sales_db"
)
```

## 🔒 Security Considerations

### Kerberos Authentication
- No credentials stored in environment variables
- Relies on system Kerberos configuration
- Requires valid Kerberos tickets
- Automatic ticket renewal may be needed

### Multi-Database Access
- Each database may have different security requirements
- Consider connection pool security
- Audit database access patterns

## 📝 Migration Guide

### From Single to Multi-Database

1. **Update Configuration:**
```bash
# Before
DEFAULT_DATABASE_NAME=oracle_db
SUPPORT_MULTIPLE_DATABASES=false

# After  
DEFAULT_DATABASE_NAME=main_db
SUPPORT_MULTIPLE_DATABASES=true
```

2. **Re-run Schema Introspection:**
```bash
# This will create new database-specific nodes
curl -X POST "http://localhost:8000/introspect-schema?database_name=main_db"
```

3. **Update Application Logic:**
- Consider database context in queries
- Update schema search to handle multiple databases
- Modify agent tools if needed

### From Username/Password to Kerberos

1. **Set up Kerberos:**
```bash
# Configure Kerberos authentication
kinit your_username@YOUR_REALM
```

2. **Update Configuration:**
```bash
ORACLE_USE_THICK_CLIENT=true
ORACLE_USE_KERBEROS=true
# Remove or comment out username/password
# ORACLE_USERNAME=
# ORACLE_PASSWORD=
```

3. **Install Oracle Libraries:**
```bash
# Ensure Oracle client libraries are available
export ORACLE_LIB_DIR=/path/to/oracle/instantclient
```

## 🐛 Troubleshooting

### Common Issues

1. **Oracle Client Library Not Found:**
```bash
# Error: DPI-1047: Cannot locate a 64-bit Oracle Client library
# Solution: Install Oracle Instant Client and set ORACLE_LIB_DIR
```

2. **Kerberos Authentication Failed:**
```bash
# Error: ORA-01017: invalid username/password
# Solution: Ensure valid Kerberos ticket with kinit
```

3. **Multi-Database Neo4j Conflicts:**
```bash
# Error: Duplicate node IDs
# Solution: Clear Neo4j database and re-run introspection
```

### Debugging

Enable debug logging:
```bash
export DEBUG=true
```

Check database connections:
```bash
curl http://localhost:8000/health
```

## 🎯 Best Practices

1. **Database Naming:** Use consistent, descriptive database names
2. **Schema Organization:** Group related schemas by database
3. **Connection Pooling:** Monitor connection pool usage
4. **Security:** Regularly rotate Kerberos tickets
5. **Monitoring:** Track schema introspection performance per database

## 📚 Examples

See `test_multi_database_example.py` for complete working examples of:
- Multi-database schema introspection
- Kerberos authentication setup
- Database-specific querying
- Cross-database relationship handling 