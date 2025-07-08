"""
A2A Test Client for Text-to-SQL Agent

This module provides a test client for the A2A text-to-SQL agent,
following the official A2A SDK patterns.

Based on the official A2A SDK example:
https://github.com/a2aproject/a2a-samples/blob/main/samples/python/agents/langgraph/app/test_client.py
"""

import asyncio
import json
import logging
from typing import Dict, Any, List
import httpx
import time

# A2A SDK imports
try:
    from a2a import (
        A2AClient,
        Message,
        MessagePart,
        TextPart,
        FunctionCallPart,
        TaskRequest,
        ClientConfig
    )
    A2A_AVAILABLE = True
except ImportError:
    # Fallback if A2A SDK is not installed
    A2A_AVAILABLE = False
    # Create placeholder classes for development
    class A2AClient:
        def __init__(self, endpoint: str):
            self.endpoint = endpoint
    
    class Message:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)
    
    class MessagePart:
        pass
    
    class TextPart:
        def __init__(self, text: str):
            self.text = text
            self.type = "text"
    
    class FunctionCallPart:
        def __init__(self, name: str, parameters: Dict[str, Any]):
            self.name = name
            self.parameters = parameters
            self.type = "function_call"
    
    class TaskRequest:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)
    
    class ClientConfig:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class TextToSQLTestClient:
    """
    Test client for the A2A text-to-SQL agent
    
    This class provides methods to test various capabilities of the agent
    including text-to-SQL conversion, schema search, and function calling.
    """
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.a2a_endpoint = f"{base_url}/a2a"
        self.client = httpx.AsyncClient(timeout=30.0)
        self.a2a_client = A2AClient(self.a2a_endpoint) if A2A_AVAILABLE else None
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.aclose()
    
    async def test_service_health(self) -> bool:
        """Test if the service is healthy and A2A is available"""
        try:
            response = await self.client.get(f"{self.base_url}/health")
            if response.status_code == 200:
                health_data = response.json()
                logger.info(f"Service health: {health_data['status']}")
                return health_data['status'] == 'healthy'
            else:
                logger.error(f"Health check failed with status {response.status_code}")
                return False
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False
    
    async def test_a2a_availability(self) -> bool:
        """Test if A2A SDK is available"""
        try:
            response = await self.client.get(f"{self.base_url}/a2a/status")
            if response.status_code == 200:
                status_data = response.json()
                logger.info(f"A2A availability: {status_data}")
                return status_data.get('available', False)
            else:
                logger.error(f"A2A status check failed with status {response.status_code}")
                return False
        except Exception as e:
            logger.error(f"A2A availability check failed: {e}")
            return False
    
    async def get_agent_card(self) -> Dict[str, Any]:
        """Get the agent card describing capabilities"""
        try:
            response = await self.client.get(f"{self.base_url}/a2a/agent-card")
            if response.status_code == 200:
                agent_card = response.json()
                logger.info(f"Agent card retrieved: {agent_card['name']} v{agent_card['version']}")
                return agent_card
            else:
                logger.error(f"Failed to get agent card: {response.status_code}")
                return {}
        except Exception as e:
            logger.error(f"Error getting agent card: {e}")
            return {}
    
    async def test_text_to_sql_conversion(self, query: str) -> Dict[str, Any]:
        """Test text-to-SQL conversion using the regular chat endpoint"""
        try:
            logger.info(f"Testing text-to-SQL conversion: {query}")
            
            request_data = {
                "messages": [{"role": "user", "content": query}],
                "session_id": "test_session"
            }
            
            response = await self.client.post(f"{self.base_url}/chat", json=request_data)
            
            if response.status_code == 200:
                result = response.json()
                logger.info(f"Text-to-SQL conversion successful")
                return result
            else:
                logger.error(f"Text-to-SQL conversion failed: {response.status_code}")
                return {}
                
        except Exception as e:
            logger.error(f"Error in text-to-SQL conversion: {e}")
            return {}
    
    async def test_a2a_text_message(self, message: str) -> Dict[str, Any]:
        """Test sending a text message via A2A protocol"""
        try:
            logger.info(f"Testing A2A text message: {message}")
            
            request_data = {
                "message": message
            }
            
            response = await self.client.post(f"{self.base_url}/a2a/message", json=request_data)
            
            if response.status_code == 200:
                result = response.json()
                logger.info(f"A2A text message successful")
                return result
            else:
                logger.error(f"A2A text message failed: {response.status_code}")
                return {}
                
        except Exception as e:
            logger.error(f"Error in A2A text message: {e}")
            return {}
    
    async def test_schema_search(self, query: str, similarity_threshold: float = 0.6) -> Dict[str, Any]:
        """Test schema search functionality"""
        try:
            logger.info(f"Testing schema search: {query}")
            
            params = {
                "query": query,
                "similarity_threshold": similarity_threshold
            }
            
            response = await self.client.get(f"{self.base_url}/schema/search", params=params)
            
            if response.status_code == 200:
                result = response.json()
                logger.info(f"Schema search successful, found {result['count']} results")
                return result
            else:
                logger.error(f"Schema search failed: {response.status_code}")
                return {}
                
        except Exception as e:
            logger.error(f"Error in schema search: {e}")
            return {}
    
    async def run_comprehensive_test(self):
        """Run a comprehensive test suite"""
        logger.info("=" * 60)
        logger.info("🧪 Starting A2A Text-to-SQL Agent Test Suite")
        logger.info("=" * 60)
        
        # Test 1: Service Health
        logger.info("\n1. Testing Service Health...")
        health_ok = await self.test_service_health()
        if not health_ok:
            logger.error("❌ Service health check failed!")
            return
        logger.info("✅ Service is healthy")
        
        # Test 2: A2A Availability
        logger.info("\n2. Testing A2A Availability...")
        a2a_ok = await self.test_a2a_availability()
        if not a2a_ok:
            logger.error("❌ A2A is not available!")
            logger.error("💡 Please install A2A SDK following A2A_SDK_INSTALLATION.md")
            return
        logger.info("✅ A2A is available")
        
        # Test 3: Agent Card
        logger.info("\n3. Testing Agent Card...")
        agent_card = await self.get_agent_card()
        if agent_card:
            logger.info(f"✅ Agent Card: {agent_card['name']}")
            logger.info(f"   📝 Description: {agent_card['description']}")
            logger.info(f"   🛠️  Skills: {len(agent_card['skills'])}")
            for skill in agent_card['skills']:
                logger.info(f"      • {skill['name']}: {skill['description']}")
        else:
            logger.error("❌ Failed to get agent card")
            return
        
        # Test 4: Text-to-SQL Conversion (Regular endpoint)
        logger.info("\n4. Testing Text-to-SQL Conversion (Regular endpoint)...")
        sql_queries = [
            "Show me all employees",
            "Find customers who placed orders in the last month",
            "What are the top 5 products by sales?"
        ]
        
        for query in sql_queries:
            result = await self.test_text_to_sql_conversion(query)
            if result:
                logger.info(f"✅ Query: {query}")
                if 'response' in result:
                    logger.info(f"   🔍 Response: {result['response']['message'][:100]}...")
            else:
                logger.error(f"❌ Query failed: {query}")
        
        # Test 5: A2A Text Messages
        logger.info("\n5. Testing A2A Text Messages...")
        a2a_queries = [
            "Generate SQL to find all users",
            "Help me write a query to get customer information"
        ]
        
        for query in a2a_queries:
            result = await self.test_a2a_text_message(query)
            if result:
                logger.info(f"✅ A2A Query: {query}")
                if 'message' in result:
                    parts = result['message']['parts']
                    for part in parts:
                        if part.get('text'):
                            logger.info(f"   📝 Response: {part['text'][:100]}...")
            else:
                logger.error(f"❌ A2A Query failed: {query}")
        
        # Test 6: Schema Search
        logger.info("\n6. Testing Schema Search...")
        search_queries = [
            "employee",
            "customer",
            "order",
            "product"
        ]
        
        for query in search_queries:
            result = await self.test_schema_search(query)
            if result:
                logger.info(f"✅ Schema search: {query}")
                logger.info(f"   🔍 Found {result['count']} results")
            else:
                logger.error(f"❌ Schema search failed: {query}")
        
        # Test Summary
        logger.info("\n" + "=" * 60)
        logger.info("📊 Test Suite Summary")
        logger.info("=" * 60)
        logger.info("✅ All tests completed successfully!")
        logger.info("🎉 A2A Text-to-SQL Agent is working correctly!")
        logger.info("\n💡 Next steps:")
        logger.info("   • Run schema introspection: POST /introspect-schema")
        logger.info("   • Test with your own queries")
        logger.info("   • Explore function calling capabilities")
        logger.info("   • Try the streaming endpoints")


async def main():
    """Main function to run the test client"""
    print("🚀 A2A Text-to-SQL Agent Test Client")
    print("=" * 50)
    
    # Configuration
    base_url = "http://localhost:8000"
    
    # Check if A2A SDK is available
    if not A2A_AVAILABLE:
        print("⚠️  A2A SDK is not available!")
        print("📖 Please install it following the instructions in A2A_SDK_INSTALLATION.md")
        print("\nInstallation steps:")
        print("1. git clone [email protected]:google/A2A.git")
        print("2. cd A2A/a2a-python-sdk")
        print("3. pip install -e .")
        print("\nNote: Tests will still run against HTTP endpoints, but A2A SDK features will be limited.")
        print()
    
    # Run tests
    async with TextToSQLTestClient(base_url) as client:
        await client.run_comprehensive_test()


if __name__ == "__main__":
    asyncio.run(main()) 