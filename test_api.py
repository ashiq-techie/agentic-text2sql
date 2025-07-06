"""
Simple test script to verify the Text-to-SQL API endpoints.
"""
import asyncio
import json
from typing import Dict, Any
import httpx
import time


class APITester:
    """Test the text-to-SQL API endpoints."""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.session_id = f"test_session_{int(time.time())}"
    
    async def test_health_check(self) -> Dict[str, Any]:
        """Test the health check endpoint."""
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{self.base_url}/health")
            return {
                "endpoint": "/health",
                "status_code": response.status_code,
                "response": response.json() if response.status_code == 200 else response.text
            }
    
    async def test_root_endpoint(self) -> Dict[str, Any]:
        """Test the root endpoint."""
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{self.base_url}/")
            return {
                "endpoint": "/",
                "status_code": response.status_code,
                "response": response.json() if response.status_code == 200 else response.text
            }
    
    async def test_chat_endpoint(self) -> Dict[str, Any]:
        """Test the chat endpoint with a sample query."""
        chat_request = {
            "messages": [
                {
                    "role": "user",
                    "content": "Hello, can you help me understand how to query the database?"
                }
            ],
            "session_id": self.session_id
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{self.base_url}/chat",
                json=chat_request
            )
            return {
                "endpoint": "/chat",
                "status_code": response.status_code,
                "response": response.json() if response.status_code == 200 else response.text
            }
    
    async def test_schema_search(self) -> Dict[str, Any]:
        """Test the schema search endpoint."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/schema/search?query=user&similarity_threshold=0.6"
            )
            return {
                "endpoint": "/schema/search",
                "status_code": response.status_code,
                "response": response.json() if response.status_code == 200 else response.text
            }
    
    async def test_metrics_endpoint(self) -> Dict[str, Any]:
        """Test the metrics endpoint."""
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{self.base_url}/metrics")
            return {
                "endpoint": "/metrics",
                "status_code": response.status_code,
                "response": response.json() if response.status_code == 200 else response.text
            }
    
    async def run_all_tests(self) -> Dict[str, Any]:
        """Run all tests and return results."""
        print("🧪 Running Text-to-SQL API Tests...")
        print("=" * 50)
        
        results = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "base_url": self.base_url,
            "session_id": self.session_id,
            "tests": {}
        }
        
        # Test 1: Root endpoint
        print("📍 Testing root endpoint...")
        try:
            result = await self.test_root_endpoint()
            results["tests"]["root"] = result
            print(f"   ✅ Status: {result['status_code']}")
        except Exception as e:
            results["tests"]["root"] = {"error": str(e)}
            print(f"   ❌ Error: {e}")
        
        # Test 2: Health check
        print("🏥 Testing health check...")
        try:
            result = await self.test_health_check()
            results["tests"]["health"] = result
            print(f"   ✅ Status: {result['status_code']}")
        except Exception as e:
            results["tests"]["health"] = {"error": str(e)}
            print(f"   ❌ Error: {e}")
        
        # Test 3: Metrics endpoint
        print("📊 Testing metrics endpoint...")
        try:
            result = await self.test_metrics_endpoint()
            results["tests"]["metrics"] = result
            print(f"   ✅ Status: {result['status_code']}")
        except Exception as e:
            results["tests"]["metrics"] = {"error": str(e)}
            print(f"   ❌ Error: {e}")
        
        # Test 4: Schema search (may fail if schema not loaded)
        print("🔍 Testing schema search...")
        try:
            result = await self.test_schema_search()
            results["tests"]["schema_search"] = result
            print(f"   ✅ Status: {result['status_code']}")
        except Exception as e:
            results["tests"]["schema_search"] = {"error": str(e)}
            print(f"   ❌ Error: {e}")
        
        # Test 5: Chat endpoint (may take longer)
        print("💬 Testing chat endpoint...")
        try:
            result = await self.test_chat_endpoint()
            results["tests"]["chat"] = result
            print(f"   ✅ Status: {result['status_code']}")
        except Exception as e:
            results["tests"]["chat"] = {"error": str(e)}
            print(f"   ❌ Error: {e}")
        
        print("=" * 50)
        print("🎯 Test Results Summary:")
        
        success_count = 0
        total_tests = len(results["tests"])
        
        for test_name, test_result in results["tests"].items():
            if "error" in test_result:
                print(f"   ❌ {test_name}: FAILED")
            elif test_result.get("status_code") == 200:
                print(f"   ✅ {test_name}: PASSED")
                success_count += 1
            else:
                print(f"   ⚠️  {test_name}: PARTIAL ({test_result.get('status_code')})")
        
        print(f"\n📈 Overall: {success_count}/{total_tests} tests passed")
        return results


async def main():
    """Run the test suite."""
    tester = APITester()
    results = await tester.run_all_tests()
    
    # Save results to file
    with open("test_results.json", "w") as f:
        json.dump(results, f, indent=2)
    
    print("\n💾 Test results saved to 'test_results.json'")
    print("\n🚀 To start the API server, run: python main.py")
    print("📚 API documentation available at: http://localhost:8000/docs")


if __name__ == "__main__":
    asyncio.run(main()) 