import pytest
from unittest.mock import MagicMock, patch
from app.services.parser import parse_sale_message

@patch("app.services.parser.client.chat.completions.create")
def test_parse_sale_message_success(mock_create):
    # Mock OpenAI response
    mock_response = MagicMock()
    mock_response.choices = [
        MagicMock(message=MagicMock(content='{"item": "rice", "quantity": 5, "unit": "bags", "amount": 200000, "customer": "Hilary"}'))
    ]
    mock_create.return_value = mock_response

    message = "I sold 5 bags of rice to Hilary for 200k"
    result = parse_sale_message(message)

    assert result["item"] == "rice"
    assert result["quantity"] == 5
    assert result["amount"] == 200000
    assert result["customer"] == "Hilary"

@patch("app.services.parser.client.chat.completions.create")
def test_parse_sale_message_unsupported(mock_create):
    # Mock OpenAI response for invalid input
    mock_response = MagicMock()
    mock_response.choices = [
        MagicMock(message=MagicMock(content='{"error": "unsupported_format"}'))
    ]
    mock_create.return_value = mock_response

    message = "Hello how are you"
    result = parse_sale_message(message)

    assert result is None
