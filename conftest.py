import pytest
import os
from unittest.mock import patch, MagicMock


@pytest.fixture(autouse=True)
def mock_openai():
    """Automatically mock OpenAI API calls for all tests to prevent real API calls."""
    with patch("conversation_topics.OpenAI") as mock_openai_class:
        # Create a mock client
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client

        # Mock the chat completion response
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = (
            "Mocked conversation topics for testing"
        )
        mock_client.chat.completions.create.return_value = mock_response

        yield mock_openai_class


@pytest.fixture(autouse=True)
def mock_environment():
    """Ensure tests don't use real environment variables that could cause slow API calls."""
    with patch.dict(
        os.environ, {"OPENAI_API_KEY": "test-key-not-real", "USE_PRINTER_DUMMY": "true"}
    ):
        yield


@pytest.fixture(autouse=True)
def mock_conversation_generator():
    """Mock the conversation topic generator to return fast, predictable results."""
    with patch(
        "conversation_topics.ConversationTopicGenerator.generate_topics"
    ) as mock_generate:
        mock_generate.return_value = """CONVERSATION TOPICS
========================================
Printed on: Test Date

1. What's a small choice we made that quietly shaped our life in a big way?
2. What's something we've adapted to that used to feel like a dealbreaker?
3. What's a way we've helped each other become more ourselves?
4. What's something about you that's hard to explain but you know I get?
5. What's one way we've protected each other's energy lately?

========================================"""
        yield mock_generate
