"""
A2A Message Handler

Utilities for processing A2A messages and converting between different formats.
"""
from typing import List, Dict, Any, Optional
import logging
from a2a_schemas import (
    Message, MessageRole, Part, TextPart, DataPart, FilePart, 
    create_text_part, create_data_part, create_user_message, create_assistant_message
)

logger = logging.getLogger(__name__)


class A2AMessageHandler:
    """
    Handler for A2A message processing and format conversion.
    
    Provides utilities to convert between A2A message formats and our
    internal agent message formats.
    """
    
    @staticmethod
    def extract_text_from_message(message: Message) -> str:
        """
        Extract text content from an A2A message.
        
        Args:
            message: A2A message
            
        Returns:
            Combined text content from all text parts
        """
        text_parts = []
        
        for part in message.parts:
            if isinstance(part, TextPart):
                text_parts.append(part.text)
            elif hasattr(part, 'text'):
                text_parts.append(part.text)
        
        return " ".join(text_parts)
    
    @staticmethod
    def extract_data_from_message(message: Message) -> List[Dict[str, Any]]:
        """
        Extract structured data from an A2A message.
        
        Args:
            message: A2A message
            
        Returns:
            List of data objects from all data parts
        """
        data_parts = []
        
        for part in message.parts:
            if isinstance(part, DataPart):
                data_parts.append(part.data)
            elif hasattr(part, 'data'):
                data_parts.append(part.data)
        
        return data_parts
    
    @staticmethod
    def convert_to_agent_format(a2a_messages: List[Message]) -> List[tuple]:
        """
        Convert A2A messages to our agent's message format.
        
        Args:
            a2a_messages: List of A2A messages
            
        Returns:
            List of (role, content) tuples
        """
        agent_messages = []
        
        for message in a2a_messages:
            role = message.role.value
            content = A2AMessageHandler.extract_text_from_message(message)
            
            if content.strip():
                agent_messages.append((role, content))
        
        return agent_messages
    
    @staticmethod
    def convert_from_agent_format(
        agent_messages: List[tuple], 
        include_data: Optional[Dict[str, Any]] = None
    ) -> List[Message]:
        """
        Convert agent messages to A2A format.
        
        Args:
            agent_messages: List of (role, content) tuples
            include_data: Optional structured data to include
            
        Returns:
            List of A2A messages
        """
        a2a_messages = []
        
        for role, content in agent_messages:
            # Create message based on role
            if role == "user":
                message = create_user_message(content)
            elif role == "assistant":
                message = create_assistant_message(content)
            else:
                # System or other roles
                message = Message(
                    role=MessageRole.SYSTEM if role == "system" else MessageRole.ASSISTANT,
                    parts=[create_text_part(content)]
                )
            
            a2a_messages.append(message)
        
        # Add structured data to the last assistant message if provided
        if include_data and a2a_messages:
            last_message = a2a_messages[-1]
            if last_message.role == MessageRole.ASSISTANT:
                last_message.parts.append(create_data_part(include_data))
        
        return a2a_messages
    
    @staticmethod
    def create_response_message(
        content: str, 
        data: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Message:
        """
        Create a response message with optional structured data.
        
        Args:
            content: Text content of the response
            data: Optional structured data
            metadata: Optional message metadata
            
        Returns:
            A2A response message
        """
        parts = [create_text_part(content)]
        
        if data:
            parts.append(create_data_part(data))
        
        return Message(
            role=MessageRole.ASSISTANT,
            parts=parts,
            metadata=metadata or {}
        )
    
    @staticmethod
    def validate_message_format(message: Message) -> bool:
        """
        Validate that a message has the correct A2A format.
        
        Args:
            message: A2A message to validate
            
        Returns:
            True if valid, False otherwise
        """
        try:
            # Check required fields
            if not hasattr(message, 'role') or not hasattr(message, 'parts'):
                return False
            
            # Check role is valid
            if message.role not in [MessageRole.USER, MessageRole.ASSISTANT, MessageRole.SYSTEM]:
                return False
            
            # Check parts are valid
            if not message.parts:
                return False
            
            # Check each part has required fields
            for part in message.parts:
                if not hasattr(part, 'type'):
                    return False
                
                if isinstance(part, TextPart) and not hasattr(part, 'text'):
                    return False
                elif isinstance(part, DataPart) and not hasattr(part, 'data'):
                    return False
                elif isinstance(part, FilePart) and not hasattr(part, 'file_data'):
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"Message validation error: {e}")
            return False
    
    @staticmethod
    def get_message_summary(message: Message) -> str:
        """
        Get a summary of the message content.
        
        Args:
            message: A2A message
            
        Returns:
            Summary string
        """
        text_content = A2AMessageHandler.extract_text_from_message(message)
        data_parts = A2AMessageHandler.extract_data_from_message(message)
        
        summary = f"Role: {message.role.value}"
        
        if text_content:
            preview = text_content[:100] + "..." if len(text_content) > 100 else text_content
            summary += f", Text: {preview}"
        
        if data_parts:
            summary += f", Data parts: {len(data_parts)}"
        
        return summary


# Global message handler instance
message_handler = A2AMessageHandler() 