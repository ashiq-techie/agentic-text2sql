"""
Test example demonstrating multi-database support and Kerberos authentication.

This example shows:
1. How to configure multiple databases
2. How to use Kerberos authentication  
3. How to introspect schemas for different databases
4. How to query database-specific schema information

Usage:
    python test_multi_database_example.py
"""

import asyncio
import os
from typing import Optional

# Set up environment for testing
os.environ.update({
    # Multi-database configuration
    "DEFAULT_DATABASE_NAME": "sales_db",
    "SUPPORT_MULTIPLE_DATABASES": "true",
    
    # Oracle thick client with Kerberos (uncomment to test)
    # "ORACLE_USE_THICK_CLIENT": "true",
    # "ORACLE_LIB_DIR": "/opt/oracle/instantclient_21_1",
    # "ORACLE_USE_KERBEROS": "true",
    
    # For testing without Kerberos
    "ORACLE_USE_THICK_CLIENT": "false",
    "ORACLE_USE_KERBEROS": "false",
    "ORACLE_USERNAME": "hr",
    "ORACLE_PASSWORD": "password",
    
    # Neo4j configuration
    "NEO4J_URI": "bolt://localhost:7687",
    "NEO4J_USERNAME": "neo4j",
    "NEO4J_PASSWORD": "password",
    
    # Other settings
    "OPENAI_API_KEY": "test-key"
})

import requests
import json

# Import after setting environment
from config import settings
from clients import initialize_clients, shutdown_clients
from schema_introspection import SchemaIntrospector


async def test_multi_database_introspection():
    """Test schema introspection for multiple databases."""
    print("🔍 Testing Multi-Database Schema Introspection")
    print("=" * 50)
    
    # Initialize clients
    await initialize_clients()
    
    try:
        # Create schema introspector
        introspector = SchemaIntrospector()
        
        # Test 1: Introspect default database
        print("\n1. Introspecting default database (sales_db)...")
        schema_graph_1 = await introspector.introspect_oracle_schema(
            schema_name="HR",  # Oracle schema within database
            database_name="sales_db"
        )
        
        print(f"   - Found {len(schema_graph_1.nodes)} nodes")
        print(f"   - Found {len(schema_graph_1.relationships)} relationships")
        
        # Store first database schema
        await introspector.store_schema_in_neo4j(schema_graph_1, "sales_db")
        print("   - Stored sales_db schema in Neo4j")
        
        # Test 2: Introspect second database  
        print("\n2. Introspecting second database (hr_db)...")
        schema_graph_2 = await introspector.introspect_oracle_schema(
            schema_name="HR",  # Same Oracle schema, different database
            database_name="hr_db"
        )
        
        print(f"   - Found {len(schema_graph_2.nodes)} nodes")
        print(f"   - Found {len(schema_graph_2.relationships)} relationships")
        
        # Store second database schema
        await introspector.store_schema_in_neo4j(schema_graph_2, "hr_db")
        print("   - Stored hr_db schema in Neo4j")
        
        # Test 3: Verify database-specific storage
        print("\n3. Verifying database-specific storage...")
        
        # Check database nodes
        db_nodes = await introspector.neo4j.query(
            "MATCH (n:SchemaNode {type: 'database'}) RETURN n.name as name, n.id as id"
        )
        
        print(f"   - Database nodes found: {len(db_nodes)}")
        for node in db_nodes:
            print(f"     * {node['name']} (ID: {node['id']})")
        
        # Check table nodes for each database
        table_nodes = await introspector.neo4j.query(
            "MATCH (n:SchemaNode {type: 'table'}) RETURN n.name as name, n.properties.database as database"
        )
        
        print(f"   - Table nodes found: {len(table_nodes)}")
        for node in table_nodes:
            print(f"     * {node['name']} (Database: {node['database']})")
        
        print("\n✅ Multi-database introspection test completed successfully!")
        
    except Exception as e:
        print(f"\n❌ Multi-database introspection test failed: {e}")
        raise
    finally:
        await shutdown_clients()


async def test_kerberos_authentication():
    """Test Kerberos authentication (requires proper setup)."""
    print("\n🔐 Testing Kerberos Authentication")
    print("=" * 50)
    
    # Check if Kerberos is enabled
    if not settings.oracle_use_kerberos:
        print("   ⚠️  Kerberos authentication is disabled")
        print("   💡 To test Kerberos:")
        print("      - Set ORACLE_USE_KERBEROS=true")
        print("      - Set ORACLE_USE_THICK_CLIENT=true")
        print("      - Ensure valid Kerberos ticket (kinit)")
        print("      - Set ORACLE_LIB_DIR to Oracle client libraries")
        return
    
    print("   ✅ Kerberos authentication is enabled")
    print(f"   📁 Oracle lib dir: {settings.oracle_lib_dir}")
    print(f"   🔧 Thick client: {settings.oracle_use_thick_client}")
    
    # Test connection
    try:
        from clients import oracle_client
        await oracle_client.connect()
        health = await oracle_client.health_check()
        
        if health:
            print("   ✅ Kerberos authentication successful!")
        else:
            print("   ❌ Kerberos authentication failed")
            
    except Exception as e:
        print(f"   ❌ Kerberos authentication error: {e}")
        print("   💡 Common issues:")
        print("      - Invalid or expired Kerberos ticket")
        print("      - Oracle client libraries not found")
        print("      - Kerberos configuration issues")


def test_api_endpoints():
    """Test the API endpoints for multi-database support."""
    print("\n🌐 Testing API Endpoints")
    print("=" * 50)
    
    base_url = "http://localhost:8000"
    
    try:
        # Test 1: Health check
        print("\n1. Testing health check...")
        response = requests.get(f"{base_url}/health")
        if response.status_code == 200:
            print("   ✅ Health check passed")
        else:
            print(f"   ❌ Health check failed: {response.status_code}")
        
        # Test 2: Schema introspection with database name
        print("\n2. Testing schema introspection with database name...")
        response = requests.post(
            f"{base_url}/introspect-schema",
            params={
                "database_name": "test_db",
                "schema_name": "HR"
            }
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"   ✅ Schema introspection started for database: {result['database_name']}")
        else:
            print(f"   ❌ Schema introspection failed: {response.status_code}")
        
        # Test 3: Schema search
        print("\n3. Testing schema search...")
        response = requests.get(
            f"{base_url}/schema/search",
            params={"query": "employee"}
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"   ✅ Schema search returned {result['count']} results")
        else:
            print(f"   ❌ Schema search failed: {response.status_code}")
        
    except requests.exceptions.ConnectionError:
        print("   ⚠️  API server not running")
        print("   💡 Start the server with: python main.py")
    except Exception as e:
        print(f"   ❌ API test failed: {e}")


async def main():
    """Run all multi-database and Kerberos tests."""
    print("🚀 Multi-Database and Kerberos Authentication Test Suite")
    print("=" * 60)
    
    print(f"\n📋 Configuration:")
    print(f"   • Default database: {settings.default_database_name}")
    print(f"   • Multi-database support: {settings.support_multiple_databases}")
    print(f"   • Oracle thick client: {settings.oracle_use_thick_client}")
    print(f"   • Kerberos authentication: {settings.oracle_use_kerberos}")
    
    # Run tests
    await test_multi_database_introspection()
    await test_kerberos_authentication()
    
    print("\n🌐 Note: API endpoint tests require running server")
    print("   Run 'python main.py' in another terminal, then run:")
    print("   python -c \"from test_multi_database_example import test_api_endpoints; test_api_endpoints()\"")


if __name__ == "__main__":
    asyncio.run(main()) 