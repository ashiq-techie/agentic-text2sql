#!/usr/bin/env python3
"""
A2A Protocol API Test Script

Test the A2A (Agent2Agent) protocol endpoints for the text-to-SQL agent.
"""
import asyncio
import json
import httpx
from typing import Dict, Any
import uuid
import time

from a2a_schemas import (
    TaskInput, TaskSendRequest, TaskSubscribeRequest, 
    create_user_message, create_assistant_message
)

# Configuration
API_BASE_URL = "http://localhost:8000"
TIMEOUT = 30.0


class A2ATestClient:
    """Client for testing A2A protocol endpoints."""
    
    def __init__(self, base_url: str = API_BASE_URL):
        self.base_url = base_url
        self.client = httpx.AsyncClient(timeout=TIMEOUT)
    
    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()
    
    async def get_agent_card(self) -> Dict[str, Any]:
        """Get the agent card."""
        response = await self.client.get(f"{self.base_url}/agent-card")
        response.raise_for_status()
        return response.json()
    
    async def send_task(self, task_request: TaskSendRequest) -> Dict[str, Any]:
        """Send a task for synchronous execution."""
        response = await self.client.post(
            f"{self.base_url}/tasks/send",
            json=task_request.dict()
        )
        response.raise_for_status()
        return response.json()
    
    async def get_task(self, task_id: str) -> Dict[str, Any]:
        """Get task status and results."""
        response = await self.client.get(f"{self.base_url}/tasks/{task_id}")
        response.raise_for_status()
        return response.json()
    
    async def send_task_streaming(self, task_request: TaskSubscribeRequest):
        """Send a task for streaming execution."""
        async with self.client.stream(
            "POST",
            f"{self.base_url}/tasks/sendSubscribe",
            json=task_request.dict()
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    try:
                        data = json.loads(line[6:])  # Remove "data: " prefix
                        yield data
                    except json.JSONDecodeError:
                        continue


async def test_agent_card():
    """Test getting the agent card."""
    print("🔍 Testing Agent Card...")
    
    client = A2ATestClient()
    try:
        card = await client.get_agent_card()
        
        print(f"✅ Agent: {card['name']}")
        print(f"✅ Version: {card['version']}")
        print(f"✅ Capabilities: {len(card['capabilities'])}")
        print(f"✅ Streaming: {card['streaming']}")
        print(f"✅ Max Concurrent Tasks: {card['max_concurrent_tasks']}")
        
        # Print capabilities
        for cap in card['capabilities']:
            print(f"  - {cap['name']}: {cap['description']}")
        
        return True
        
    except Exception as e:
        print(f"❌ Agent Card test failed: {e}")
        return False
    finally:
        await client.close()


async def test_simple_task():
    """Test sending a simple task."""
    print("\n🔍 Testing Simple Task...")
    
    client = A2ATestClient()
    try:
        # Create a simple text-to-SQL task
        user_message = create_user_message("Show me all tables in the database")
        
        task_request = TaskSendRequest(
            input=TaskInput(messages=[user_message]),
            metadata={"test": "simple_task"}
        )
        
        # Send the task
        response = await client.send_task(task_request)
        task_id = response["task_id"]
        
        print(f"✅ Task created: {task_id}")
        print(f"✅ Status: {response['status']}")
        
        # Get task results
        task_result = await client.get_task(task_id)
        task = task_result["task"]
        
        print(f"✅ Final Status: {task['state']['status']}")
        print(f"✅ Status Message: {task['state']['status_message']}")
        
        if task['output']:
            print(f"✅ Output Messages: {len(task['output']['messages'])}")
            print(f"✅ Output Artefacts: {len(task['output']['artefacts'])}")
            
            # Print first message
            if task['output']['messages']:
                first_msg = task['output']['messages'][0]
                print(f"✅ Response: {first_msg['parts'][0]['text'][:100]}...")
        
        return True
        
    except Exception as e:
        print(f"❌ Simple task test failed: {e}")
        return False
    finally:
        await client.close()


async def test_sql_query_task():
    """Test a SQL query generation task."""
    print("\n🔍 Testing SQL Query Task...")
    
    client = A2ATestClient()
    try:
        # Create a SQL query task
        user_message = create_user_message("Find all customers from the lifecycle table where status is active")
        
        task_request = TaskSendRequest(
            input=TaskInput(messages=[user_message]),
            metadata={"test": "sql_query_task"}
        )
        
        # Send the task
        response = await client.send_task(task_request)
        task_id = response["task_id"]
        
        print(f"✅ Task created: {task_id}")
        
        # Get task results
        task_result = await client.get_task(task_id)
        task = task_result["task"]
        
        print(f"✅ Final Status: {task['state']['status']}")
        
        if task['output']:
            # Look for SQL query in artefacts
            for artefact in task['output']['artefacts']:
                if artefact['title'] == 'Generated SQL Query':
                    print(f"✅ Found SQL Query Artefact")
                    for part in artefact['parts']:
                        if part['type'] == 'text':
                            print(f"✅ SQL: {part['text']}")
                        elif part['type'] == 'data':
                            print(f"✅ Query Data: {part['data']}")
        
        return True
        
    except Exception as e:
        print(f"❌ SQL query task test failed: {e}")
        return False
    finally:
        await client.close()


async def test_streaming_task():
    """Test streaming task execution."""
    print("\n🔍 Testing Streaming Task...")
    
    client = A2ATestClient()
    try:
        # Create a streaming task
        user_message = create_user_message("Generate a complex query to find product sales by category")
        
        task_request = TaskSubscribeRequest(
            input=TaskInput(messages=[user_message]),
            metadata={"test": "streaming_task"}
        )
        
        # Send the streaming task
        events = []
        async for event in client.send_task_streaming(task_request):
            events.append(event)
            print(f"📡 Event: {event}")
            
            # Stop after completion or error
            if event.get("event") in ["task_complete", "task_error"]:
                break
        
        print(f"✅ Received {len(events)} events")
        
        # Check for expected events
        event_types = [event.get("event") for event in events]
        expected_events = ["task_progress", "task_complete"]
        
        for expected in expected_events:
            if expected in event_types:
                print(f"✅ Found expected event: {expected}")
            else:
                print(f"⚠️  Missing expected event: {expected}")
        
        return True
        
    except Exception as e:
        print(f"❌ Streaming task test failed: {e}")
        return False
    finally:
        await client.close()


async def test_schema_exploration():
    """Test schema exploration capabilities."""
    print("\n🔍 Testing Schema Exploration...")
    
    client = A2ATestClient()
    try:
        # Test schema search query
        user_message = create_user_message("What tables are available for customer data?")
        
        task_request = TaskSendRequest(
            input=TaskInput(messages=[user_message]),
            metadata={"test": "schema_exploration"}
        )
        
        # Send the task
        response = await client.send_task(task_request)
        task_id = response["task_id"]
        
        print(f"✅ Task created: {task_id}")
        
        # Get task results
        task_result = await client.get_task(task_id)
        task = task_result["task"]
        
        print(f"✅ Final Status: {task['state']['status']}")
        
        if task['output'] and task['output']['messages']:
            response_text = task['output']['messages'][0]['parts'][0]['text']
            print(f"✅ Response: {response_text[:200]}...")
        
        return True
        
    except Exception as e:
        print(f"❌ Schema exploration test failed: {e}")
        return False
    finally:
        await client.close()


async def test_error_handling():
    """Test error handling."""
    print("\n🔍 Testing Error Handling...")
    
    client = A2ATestClient()
    try:
        # Create an invalid task (empty message)
        user_message = create_user_message("")
        
        task_request = TaskSendRequest(
            input=TaskInput(messages=[user_message]),
            metadata={"test": "error_handling"}
        )
        
        # Send the task
        response = await client.send_task(task_request)
        task_id = response["task_id"]
        
        print(f"✅ Task created: {task_id}")
        
        # Get task results
        task_result = await client.get_task(task_id)
        task = task_result["task"]
        
        print(f"✅ Final Status: {task['state']['status']}")
        print(f"✅ Status Message: {task['state']['status_message']}")
        
        # Should handle empty query gracefully
        if task['state']['status'] in ['completed', 'failed']:
            print("✅ Error handling working properly")
        
        return True
        
    except Exception as e:
        print(f"❌ Error handling test failed: {e}")
        return False
    finally:
        await client.close()


async def run_all_tests():
    """Run all A2A protocol tests."""
    print("🚀 Starting A2A Protocol Tests...")
    print("=" * 50)
    
    tests = [
        test_agent_card,
        test_simple_task,
        test_sql_query_task,
        test_streaming_task,
        test_schema_exploration,
        test_error_handling,
    ]
    
    results = []
    
    for test_func in tests:
        try:
            result = await test_func()
            results.append(result)
        except Exception as e:
            print(f"❌ Test {test_func.__name__} failed with exception: {e}")
            results.append(False)
    
    print("\n" + "=" * 50)
    print("📊 Test Results:")
    print(f"✅ Passed: {sum(results)}")
    print(f"❌ Failed: {len(results) - sum(results)}")
    print(f"📈 Success Rate: {sum(results) / len(results) * 100:.1f}%")
    
    if all(results):
        print("\n🎉 All A2A Protocol tests passed!")
    else:
        print("\n⚠️  Some tests failed. Check the API server and try again.")
    
    return all(results)


async def main():
    """Main test execution."""
    print("A2A Protocol Test Suite")
    print("======================")
    print("Make sure the API server is running on http://localhost:8000")
    print("")
    
    # Wait a moment for user to read
    await asyncio.sleep(2)
    
    # Run tests
    success = await run_all_tests()
    
    if success:
        print("\n✅ All tests completed successfully!")
        exit(0)
    else:
        print("\n❌ Some tests failed!")
        exit(1)


if __name__ == "__main__":
    asyncio.run(main()) 