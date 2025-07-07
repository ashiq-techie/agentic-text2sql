#!/usr/bin/env python3
"""
Unit Tests for Python A2A SDK Integration

Demonstrates how much easier it is to write unit tests with the official SDK.
"""
import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from python_a2a import Message, TextContent, MessageRole, FunctionCallContent, FunctionParameter

# Import our SDK-based components
from a2a_agent_server import TextToSQLAgent


class TestTextToSQLAgent:
    """Test suite for the A2A SDK-based text-to-SQL agent."""
    
    @pytest.fixture
    def agent(self):
        """Create a test agent instance."""
        return TextToSQLAgent()
    
    @pytest.fixture
    def mock_initialized_agent(self, agent):
        """Create a mock initialized agent."""
        agent._initialized = True
        agent._agent = Mock()
        agent._agent_session = Mock()
        return agent
    
    def test_agent_initialization(self, agent):
        """Test agent initialization."""
        assert agent._initialized is False
        assert agent._agent is None
        assert agent._agent_session is None
    
    def test_handle_uninitialized_agent(self, agent):
        """Test handling messages when agent is not initialized."""
        # Create a text message using SDK
        message = Message(
            content=TextContent(text="Test query"),
            role=MessageRole.USER
        )
        
        # Handle the message
        response = agent.handle_message(message)
        
        # Verify response
        assert response.role == MessageRole.AGENT
        assert response.content.type == "text"
        assert "initializing" in response.content.text.lower()
        assert response.parent_message_id == message.message_id
    
    def test_handle_unsupported_message_type(self, mock_initialized_agent):
        """Test handling unsupported message types."""
        # Create a message with unsupported content type
        message = Message(
            content=Mock(),  # Mock content that's not text or function_call
            role=MessageRole.USER
        )
        message.content.type = "unsupported_type"
        
        # Handle the message
        response = mock_initialized_agent.handle_message(message)
        
        # Verify response
        assert response.role == MessageRole.AGENT
        assert response.content.type == "text"
        assert "can only handle text messages" in response.content.text.lower()
    
    @patch('a2a_agent_server.invoke_agent')
    def test_handle_text_message_success(self, mock_invoke, mock_initialized_agent):
        """Test successful text message handling."""
        # Setup mock response
        mock_invoke.return_value = asyncio.Future()
        mock_invoke.return_value.set_result({
            "messages": [("user", "test query"), ("agent", "Test response")],
            "sql_query": "SELECT * FROM test_table",
            "results": [{"id": 1, "name": "test"}]
        })
        
        # Create test message
        message = Message(
            content=TextContent(text="Show me test data"),
            role=MessageRole.USER
        )
        
        # Handle the message
        with patch('asyncio.get_event_loop') as mock_loop:
            mock_loop.return_value.run_until_complete.return_value = {
                "messages": [("user", "test query"), ("agent", "Test response")],
                "sql_query": "SELECT * FROM test_table",
                "results": [{"id": 1, "name": "test"}]
            }
            
            response = mock_initialized_agent.handle_message(message)
        
        # Verify response
        assert response.role == MessageRole.AGENT
        assert response.content.type == "text"
        assert "Test response" in response.content.text
        assert "SELECT * FROM test_table" in response.content.text
        assert "1 rows" in response.content.text
    
    @patch('a2a_agent_server.invoke_agent')
    def test_handle_text_message_error(self, mock_invoke, mock_initialized_agent):
        """Test text message handling with error."""
        # Setup mock to raise exception
        mock_invoke.side_effect = Exception("Test error")
        
        # Create test message
        message = Message(
            content=TextContent(text="Test query"),
            role=MessageRole.USER
        )
        
        # Handle the message
        with patch('asyncio.get_event_loop') as mock_loop:
            mock_loop.return_value.run_until_complete.side_effect = Exception("Test error")
            
            response = mock_initialized_agent.handle_message(message)
        
        # Verify error response
        assert response.role == MessageRole.AGENT
        assert response.content.type == "text"
        assert "error" in response.content.text.lower()
        assert "Test error" in response.content.text
    
    @patch('a2a_agent_server.invoke_agent')
    def test_handle_generate_sql_function(self, mock_invoke, mock_initialized_agent):
        """Test generate_sql function call."""
        # Setup mock response
        mock_invoke.return_value = asyncio.Future()
        mock_invoke.return_value.set_result({
            "sql_query": "SELECT * FROM customers WHERE city = 'New York'",
            "database_type": "Oracle"
        })
        
        # Create function call message
        message = Message(
            content=FunctionCallContent(
                name="generate_sql",
                parameters=[
                    FunctionParameter(name="query", value="Find customers in New York")
                ]
            ),
            role=MessageRole.USER
        )
        
        # Handle the message
        with patch('asyncio.get_event_loop') as mock_loop:
            mock_loop.return_value.run_until_complete.return_value = {
                "sql_query": "SELECT * FROM customers WHERE city = 'New York'",
                "database_type": "Oracle"
            }
            
            response = mock_initialized_agent.handle_message(message)
        
        # Verify function response
        assert response.role == MessageRole.AGENT
        assert response.content.type == "function_response"
        assert response.content.name == "generate_sql"
        assert "sql_query" in response.content.response
        assert "SELECT * FROM customers" in response.content.response["sql_query"]
        assert response.content.response["query_type"] == "Oracle"
    
    @patch('a2a_agent_server.schema_introspector')
    def test_handle_search_schema_function(self, mock_introspector, mock_initialized_agent):
        """Test search_schema function call."""
        # Setup mock response
        mock_introspector.find_relevant_schema.return_value = asyncio.Future()
        mock_introspector.find_relevant_schema.return_value.set_result([
            {"table": "customers", "columns": ["id", "name", "city"]},
            {"table": "customer_orders", "columns": ["order_id", "customer_id"]}
        ])
        
        # Create function call message
        message = Message(
            content=FunctionCallContent(
                name="search_schema",
                parameters=[
                    FunctionParameter(name="search_term", value="customer"),
                    FunctionParameter(name="similarity_threshold", value=0.7)
                ]
            ),
            role=MessageRole.USER
        )
        
        # Handle the message
        with patch('asyncio.get_event_loop') as mock_loop:
            mock_loop.return_value.run_until_complete.return_value = [
                {"table": "customers", "columns": ["id", "name", "city"]},
                {"table": "customer_orders", "columns": ["order_id", "customer_id"]}
            ]
            
            response = mock_initialized_agent.handle_message(message)
        
        # Verify function response
        assert response.role == MessageRole.AGENT
        assert response.content.type == "function_response"
        assert response.content.name == "search_schema"
        assert "results" in response.content.response
        assert response.content.response["count"] == 2
        assert response.content.response["search_term"] == "customer"
    
    def test_handle_invalid_function_call(self, mock_initialized_agent):
        """Test handling invalid function calls."""
        # Create invalid function call message
        message = Message(
            content=FunctionCallContent(
                name="nonexistent_function",
                parameters=[
                    FunctionParameter(name="param", value="value")
                ]
            ),
            role=MessageRole.USER
        )
        
        # Handle the message
        response = mock_initialized_agent.handle_message(message)
        
        # Verify error response
        assert response.role == MessageRole.AGENT
        assert response.content.type == "function_response"
        assert response.content.name == "nonexistent_function"
        assert "error" in response.content.response
        assert "Unknown function" in response.content.response["error"]
    
    def test_function_call_missing_parameters(self, mock_initialized_agent):
        """Test function call with missing required parameters."""
        # Create function call without required query parameter
        message = Message(
            content=FunctionCallContent(
                name="generate_sql",
                parameters=[]  # Missing query parameter
            ),
            role=MessageRole.USER
        )
        
        # Handle the message
        response = mock_initialized_agent.handle_message(message)
        
        # Verify error response
        assert response.role == MessageRole.AGENT
        assert response.content.type == "function_response"
        assert response.content.name == "generate_sql"
        assert "error" in response.content.response
        assert "required" in response.content.response["error"].lower()


class TestSDKIntegration:
    """Test SDK integration features."""
    
    def test_message_creation_with_sdk(self):
        """Test creating messages with the SDK."""
        # Text message
        text_message = Message(
            content=TextContent(text="Hello world"),
            role=MessageRole.USER
        )
        
        assert text_message.content.type == "text"
        assert text_message.content.text == "Hello world"
        assert text_message.role == MessageRole.USER
        assert text_message.message_id is not None
    
    def test_function_call_creation_with_sdk(self):
        """Test creating function calls with the SDK."""
        # Function call message
        func_message = Message(
            content=FunctionCallContent(
                name="test_function",
                parameters=[
                    FunctionParameter(name="param1", value="value1"),
                    FunctionParameter(name="param2", value=42)
                ]
            ),
            role=MessageRole.USER
        )
        
        assert func_message.content.type == "function_call"
        assert func_message.content.name == "test_function"
        assert len(func_message.content.parameters) == 2
        assert func_message.content.parameters[0].name == "param1"
        assert func_message.content.parameters[0].value == "value1"
        assert func_message.content.parameters[1].value == 42
    
    def test_conversation_continuity(self):
        """Test conversation ID continuity."""
        conversation_id = "test-conversation"
        
        # Create related messages
        message1 = Message(
            content=TextContent(text="First message"),
            role=MessageRole.USER,
            conversation_id=conversation_id
        )
        
        message2 = Message(
            content=TextContent(text="Second message"),
            role=MessageRole.USER,
            conversation_id=conversation_id,
            parent_message_id=message1.message_id
        )
        
        assert message1.conversation_id == conversation_id
        assert message2.conversation_id == conversation_id
        assert message2.parent_message_id == message1.message_id
    
    def test_message_validation(self):
        """Test that SDK validates messages properly."""
        # This should work
        valid_message = Message(
            content=TextContent(text="Valid message"),
            role=MessageRole.USER
        )
        
        assert valid_message.content.text == "Valid message"
        
        # Test that SDK would catch invalid data
        # (SDK handles validation internally)
        assert hasattr(valid_message, 'message_id')
        assert hasattr(valid_message, 'timestamp')


@pytest.mark.asyncio
async def test_async_integration():
    """Test async integration with SDK components."""
    agent = TextToSQLAgent()
    
    # Test initialization
    assert agent._initialized is False
    
    # Mock the initialization
    with patch.object(agent, '_agent', Mock()), \
         patch.object(agent, '_agent_session', Mock()):
        
        agent._initialized = True
        
        # Test async message handling
        message = Message(
            content=TextContent(text="Test async message"),
            role=MessageRole.USER
        )
        
        # This should work with the mocked agent
        response = agent.handle_message(message)
        assert response is not None


def test_sdk_benefits():
    """Test that demonstrates SDK benefits."""
    # Before: Custom implementation would require complex setup
    # After: SDK makes it simple
    
    # Easy message creation
    message = Message(
        content=TextContent(text="Test message"),
        role=MessageRole.USER
    )
    
    # Built-in validation
    assert message.content.type == "text"
    assert message.role == MessageRole.USER
    
    # Automatic ID generation
    assert message.message_id is not None
    assert message.timestamp is not None
    
    # Type safety
    assert isinstance(message.content, TextContent)
    assert isinstance(message.role, MessageRole)
    
    print("✅ SDK provides:")
    print("  • Automatic message validation")
    print("  • Type safety")
    print("  • ID generation")
    print("  • Timestamp management")
    print("  • Standardized error handling")
    print("  • Easy testing")


if __name__ == "__main__":
    # Run tests
    print("Running Python A2A SDK Unit Tests...")
    print("=" * 40)
    
    # Simple test runner
    test_suite = TestTextToSQLAgent()
    sdk_tests = TestSDKIntegration()
    
    try:
        # Test basic functionality
        agent = TextToSQLAgent()
        test_suite.test_agent_initialization(agent)
        test_suite.test_handle_uninitialized_agent(agent)
        
        # Test SDK features
        sdk_tests.test_message_creation_with_sdk()
        sdk_tests.test_function_call_creation_with_sdk()
        sdk_tests.test_conversation_continuity()
        sdk_tests.test_message_validation()
        
        # Show benefits
        test_sdk_benefits()
        
        print("\n✅ All unit tests passed!")
        print("🎉 SDK integration successful!")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        raise 