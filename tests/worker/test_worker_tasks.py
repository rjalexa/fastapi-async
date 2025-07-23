"""Tests for Celery worker tasks."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from src.worker.tasks import summarize_text_with_pybreaker, extract_pdf_with_pybreaker, PermanentError, TransientError


@pytest.mark.asyncio
async def test_summarize_text_success(mock_openrouter_response):
    """Test that the summarize_text task works correctly."""
    # Mock the dependencies
    with patch("src.worker.tasks.get_async_redis_connection") as mock_redis, \
         patch("src.worker.tasks.call_openrouter_api", new_callable=AsyncMock) as mock_api_call, \
         patch("src.worker.tasks.load_prompt") as mock_load_prompt:
        
        # Setup mocks
        mock_redis.return_value = AsyncMock()
        mock_api_call.return_value = "This is a test summary of the provided content."
        mock_load_prompt.return_value = "You are a helpful assistant that summarizes text."
        
        # Mock the OpenRouterStateManager - it's imported inside the function
        with patch("src.api.openrouter_state.OpenRouterStateManager") as mock_state_manager:
            mock_manager_instance = AsyncMock()
            mock_manager_instance.should_skip_api_call.return_value = (False, None)
            mock_state_manager.return_value = mock_manager_instance
            
            # Call the task function directly
            result = await summarize_text_with_pybreaker("This is a long text that needs to be summarized.")
            
            # Assert the result
            assert "test summary" in result.lower()
            # Assert that the API was called
            mock_api_call.assert_called_once()


@pytest.mark.asyncio
async def test_summarize_text_api_error():
    """Test that the summarize_text task handles API errors."""
    # Mock the dependencies to raise an exception
    with patch("src.worker.tasks.get_async_redis_connection") as mock_redis, \
         patch("src.worker.tasks.call_openrouter_api") as mock_api_call, \
         patch("src.worker.tasks.load_prompt") as mock_load_prompt:
        
        # Setup mocks
        mock_redis.return_value = AsyncMock()
        mock_api_call.side_effect = Exception("API Error")
        mock_load_prompt.return_value = "You are a helpful assistant that summarizes text."
        
        # Mock the OpenRouterStateManager - it's imported inside the function
        with patch("src.api.openrouter_state.OpenRouterStateManager") as mock_state_manager:
            mock_manager_instance = AsyncMock()
            mock_manager_instance.should_skip_api_call.return_value = (False, None)
            mock_state_manager.return_value = mock_manager_instance
            
            # Call the task function and expect an exception
            with pytest.raises(TransientError):
                await summarize_text_with_pybreaker("This is a long text that needs to be summarized.")


@pytest.mark.asyncio
async def test_pdfxtract_success():
    """Test that the pdfxtract task works correctly."""
    # Mock all the dependencies
    with patch("src.worker.tasks.get_async_redis_connection") as mock_redis, \
         patch("src.worker.tasks.call_openrouter_api") as mock_api_call, \
         patch("src.worker.tasks.load_prompt") as mock_load_prompt, \
         patch("src.worker.tasks.base64.b64decode") as mock_b64decode, \
         patch("src.worker.tasks.convert_from_bytes") as mock_convert:
        
        # Setup mocks
        mock_redis.return_value = AsyncMock()
        mock_load_prompt.return_value = "Extract articles from this newspaper page."
        mock_b64decode.return_value = b"fake_pdf_bytes"
        
        # Mock PIL Image
        mock_image = MagicMock()
        mock_image.save = MagicMock()
        mock_convert.return_value = [mock_image]
        
        # Mock the API response
        mock_api_response = '{"pages": [{"page_number": 1, "articles": [{"title": "Test Article", "content": "Test content"}]}]}'
        mock_api_call.return_value = mock_api_response
        
        # Mock the OpenRouterStateManager - it's imported inside the function
        with patch("src.api.openrouter_state.OpenRouterStateManager") as mock_state_manager:
            mock_manager_instance = AsyncMock()
            mock_manager_instance.should_skip_api_call.return_value = (False, None)
            mock_state_manager.return_value = mock_manager_instance
            
            # Call the task function
            sample_pdf_content = "dGVzdCBwZGYgY29udGVudA=="  # base64 encoded "test pdf content"
            result = await extract_pdf_with_pybreaker(sample_pdf_content, "test.pdf")
            
            # The result should be a JSON string
            assert isinstance(result, str)
            # The result should contain the expected structure
            assert "filename" in result
            assert "test.pdf" in result
            assert "pages" in result


@pytest.mark.asyncio
async def test_summarize_text_missing_api_key():
    """Test that the summarize_text task handles missing API key."""
    # Mock settings to have no API key
    with patch("src.worker.tasks.settings") as mock_settings:
        mock_settings.openrouter_api_key = None
        
        # Call the task function and expect a PermanentError
        with pytest.raises(PermanentError, match="OpenRouter API key not configured"):
            await summarize_text_with_pybreaker("This is a test text.")


@pytest.mark.asyncio
async def test_pdfxtract_missing_api_key():
    """Test that the pdfxtract task handles missing API key."""
    # Mock settings to have no API key
    with patch("src.worker.tasks.settings") as mock_settings:
        mock_settings.openrouter_api_key = None
        
        # Call the task function and expect a PermanentError
        with pytest.raises(PermanentError, match="OpenRouter API key not configured"):
            await extract_pdf_with_pybreaker("dGVzdA==", "test.pdf")


@pytest.mark.asyncio
async def test_summarize_text_state_manager_skip():
    """Test that the summarize_text task respects state manager skip decision."""
    with patch("src.worker.tasks.get_async_redis_connection") as mock_redis, \
         patch("src.worker.tasks.load_prompt") as mock_load_prompt:
        
        # Setup mocks
        mock_redis.return_value = AsyncMock()
        mock_load_prompt.return_value = "You are a helpful assistant that summarizes text."
        
        # Mock the OpenRouterStateManager to indicate skip
        with patch("src.api.openrouter_state.OpenRouterStateManager") as mock_state_manager:
            mock_manager_instance = AsyncMock()
            mock_manager_instance.should_skip_api_call.return_value = (True, "Service temporarily unavailable")
            mock_state_manager.return_value = mock_manager_instance
            
            # Call the task function and expect a TransientError
            with pytest.raises(TransientError, match="OpenRouter service unavailable: Service temporarily unavailable"):
                await summarize_text_with_pybreaker("This is a test text.")


@pytest.mark.asyncio
async def test_pdfxtract_state_manager_skip():
    """Test that the pdfxtract task respects state manager skip decision."""
    with patch("src.worker.tasks.get_async_redis_connection") as mock_redis, \
         patch("src.worker.tasks.load_prompt") as mock_load_prompt:
        
        # Setup mocks
        mock_redis.return_value = AsyncMock()
        mock_load_prompt.return_value = "Extract articles from this newspaper page."
        
        # Mock the OpenRouterStateManager to indicate skip
        with patch("src.api.openrouter_state.OpenRouterStateManager") as mock_state_manager:
            mock_manager_instance = AsyncMock()
            mock_manager_instance.should_skip_api_call.return_value = (True, "Rate limit exceeded")
            mock_state_manager.return_value = mock_manager_instance
            
            # Call the task function and expect a TransientError
            with pytest.raises(TransientError, match="OpenRouter service unavailable: Rate limit exceeded"):
                await extract_pdf_with_pybreaker("dGVzdA==", "test.pdf")


@pytest.mark.asyncio
async def test_summarize_text_prompt_loading_error():
    """Test that the summarize_text task handles prompt loading errors."""
    with patch("src.worker.tasks.get_async_redis_connection") as mock_redis, \
         patch("src.worker.tasks.load_prompt") as mock_load_prompt:
        
        # Setup mocks
        mock_redis.return_value = AsyncMock()
        mock_load_prompt.side_effect = FileNotFoundError("Prompt file not found")
        
        # Mock the OpenRouterStateManager
        with patch("src.api.openrouter_state.OpenRouterStateManager") as mock_state_manager:
            mock_manager_instance = AsyncMock()
            mock_manager_instance.should_skip_api_call.return_value = (False, None)
            mock_state_manager.return_value = mock_manager_instance
            
            # Call the task function and expect a PermanentError
            with pytest.raises(PermanentError, match="Prompt error: Prompt file not found"):
                await summarize_text_with_pybreaker("This is a test text.")


@pytest.mark.asyncio
async def test_pdfxtract_prompt_loading_error():
    """Test that the pdfxtract task handles prompt loading errors."""
    with patch("src.worker.tasks.get_async_redis_connection") as mock_redis, \
         patch("src.worker.tasks.load_prompt") as mock_load_prompt:
        
        # Setup mocks
        mock_redis.return_value = AsyncMock()
        mock_load_prompt.side_effect = ValueError("Invalid prompt format")
        
        # Mock the OpenRouterStateManager
        with patch("src.api.openrouter_state.OpenRouterStateManager") as mock_state_manager:
            mock_manager_instance = AsyncMock()
            mock_manager_instance.should_skip_api_call.return_value = (False, None)
            mock_state_manager.return_value = mock_manager_instance
            
            # Call the task function and expect a PermanentError
            with pytest.raises(PermanentError, match="PDF extraction error: Invalid prompt format"):
                await extract_pdf_with_pybreaker("dGVzdA==", "test.pdf")


@pytest.mark.asyncio
async def test_pdfxtract_poppler_dependency_error():
    """Test that the pdfxtract task handles poppler dependency errors."""
    with patch("src.worker.tasks.get_async_redis_connection") as mock_redis, \
         patch("src.worker.tasks.load_prompt") as mock_load_prompt, \
         patch("src.worker.tasks.base64.b64decode") as mock_b64decode, \
         patch("src.worker.tasks.convert_from_bytes") as mock_convert:
        
        # Setup mocks
        mock_redis.return_value = AsyncMock()
        mock_load_prompt.return_value = "Extract articles from this newspaper page."
        mock_b64decode.return_value = b"fake_pdf_bytes"
        
        # Mock convert_from_bytes to raise a poppler error
        mock_convert.side_effect = Exception("poppler not installed and in PATH")
        
        # Mock the OpenRouterStateManager
        with patch("src.api.openrouter_state.OpenRouterStateManager") as mock_state_manager:
            mock_manager_instance = AsyncMock()
            mock_manager_instance.should_skip_api_call.return_value = (False, None)
            mock_state_manager.return_value = mock_manager_instance
            
            # Call the task function and expect a PermanentError
            with pytest.raises(PermanentError, match="PDF extraction dependency error: poppler not installed and in PATH"):
                await extract_pdf_with_pybreaker("dGVzdA==", "test.pdf")


@pytest.mark.asyncio
async def test_pdfxtract_malformed_json_response():
    """Test that the pdfxtract task handles malformed JSON responses."""
    with patch("src.worker.tasks.get_async_redis_connection") as mock_redis, \
         patch("src.worker.tasks.call_openrouter_api") as mock_api_call, \
         patch("src.worker.tasks.load_prompt") as mock_load_prompt, \
         patch("src.worker.tasks.base64.b64decode") as mock_b64decode, \
         patch("src.worker.tasks.convert_from_bytes") as mock_convert:
        
        # Setup mocks
        mock_redis.return_value = AsyncMock()
        mock_load_prompt.return_value = "Extract articles from this newspaper page."
        mock_b64decode.return_value = b"fake_pdf_bytes"
        
        # Mock PIL Image
        mock_image = MagicMock()
        mock_image.save = MagicMock()
        mock_convert.return_value = [mock_image]
        
        # Mock the API response with malformed JSON
        mock_api_call.return_value = "This is not valid JSON"
        
        # Mock the OpenRouterStateManager
        with patch("src.api.openrouter_state.OpenRouterStateManager") as mock_state_manager:
            mock_manager_instance = AsyncMock()
            mock_manager_instance.should_skip_api_call.return_value = (False, None)
            mock_state_manager.return_value = mock_manager_instance
            
            # Call the task function
            result = await extract_pdf_with_pybreaker("dGVzdA==", "test.pdf")
            
            # The result should still be valid JSON with a skipped page
            import json
            parsed_result = json.loads(result)
            assert "filename" in parsed_result
            assert "pages" in parsed_result
            assert len(parsed_result["pages"]) == 1
            assert parsed_result["pages"][0]["status"] == "skipped"
            assert "JSON parsing failed" in parsed_result["pages"][0]["reason"]


@pytest.mark.asyncio
async def test_pdfxtract_page_processing_failure():
    """Test that the pdfxtract task handles individual page processing failures."""
    with patch("src.worker.tasks.get_async_redis_connection") as mock_redis, \
         patch("src.worker.tasks.call_openrouter_api") as mock_api_call, \
         patch("src.worker.tasks.load_prompt") as mock_load_prompt, \
         patch("src.worker.tasks.base64.b64decode") as mock_b64decode, \
         patch("src.worker.tasks.convert_from_bytes") as mock_convert:
        
        # Setup mocks
        mock_redis.return_value = AsyncMock()
        mock_load_prompt.return_value = "Extract articles from this newspaper page."
        mock_b64decode.return_value = b"fake_pdf_bytes"
        
        # Mock PIL Image that fails during save
        mock_image = MagicMock()
        mock_image.save.side_effect = Exception("Image save failed")
        mock_convert.return_value = [mock_image]
        
        # Mock the OpenRouterStateManager
        with patch("src.api.openrouter_state.OpenRouterStateManager") as mock_state_manager:
            mock_manager_instance = AsyncMock()
            mock_manager_instance.should_skip_api_call.return_value = (False, None)
            mock_state_manager.return_value = mock_manager_instance
            
            # Call the task function
            result = await extract_pdf_with_pybreaker("dGVzdA==", "test.pdf")
            
            # The result should still be valid JSON with a skipped page
            import json
            parsed_result = json.loads(result)
            assert "filename" in parsed_result
            assert "pages" in parsed_result
            assert len(parsed_result["pages"]) == 1
            assert parsed_result["pages"][0]["status"] == "skipped"
            assert "Page processing failed" in parsed_result["pages"][0]["reason"]


@pytest.mark.asyncio
async def test_summarize_text_circuit_breaker_error():
    """Test that the summarize_text task handles circuit breaker errors."""
    with patch("src.worker.tasks.get_async_redis_connection") as mock_redis, \
         patch("src.worker.tasks.call_openrouter_api") as mock_api_call, \
         patch("src.worker.tasks.load_prompt") as mock_load_prompt:
        
        # Setup mocks
        mock_redis.return_value = AsyncMock()
        mock_api_call.side_effect = Exception("Circuit breaker is open")
        mock_load_prompt.return_value = "You are a helpful assistant that summarizes text."
        
        # Mock the OpenRouterStateManager
        with patch("src.api.openrouter_state.OpenRouterStateManager") as mock_state_manager:
            mock_manager_instance = AsyncMock()
            mock_manager_instance.should_skip_api_call.return_value = (False, None)
            mock_state_manager.return_value = mock_manager_instance
            
            # Call the task function and expect a TransientError
            with pytest.raises(TransientError, match="OpenRouter service protection: Circuit breaker is open"):
                await summarize_text_with_pybreaker("This is a test text.")


@pytest.mark.asyncio
async def test_summarize_text_status_code_parsing():
    """Test that the summarize_text task correctly parses status codes from error messages."""
    with patch("src.worker.tasks.get_async_redis_connection") as mock_redis, \
         patch("src.worker.tasks.call_openrouter_api") as mock_api_call, \
         patch("src.worker.tasks.load_prompt") as mock_load_prompt:
        
        # Setup mocks
        mock_redis.return_value = AsyncMock()
        mock_load_prompt.return_value = "You are a helpful assistant that summarizes text."
        
        # Mock the OpenRouterStateManager
        with patch("src.api.openrouter_state.OpenRouterStateManager") as mock_state_manager:
            mock_manager_instance = AsyncMock()
            mock_manager_instance.should_skip_api_call.return_value = (False, None)
            mock_state_manager.return_value = mock_manager_instance
            
            # Test permanent error with status code
            mock_api_call.side_effect = Exception("API error status_code=401 Unauthorized")
            with pytest.raises(PermanentError, match="OpenRouter API error: API error status_code=401 Unauthorized"):
                await summarize_text_with_pybreaker("This is a test text.")
            
            # Test transient error with status code
            mock_api_call.side_effect = Exception("API error status_code=429 Rate limited")
            with pytest.raises(TransientError) as exc_info:
                await summarize_text_with_pybreaker("This is a test text.")
            assert exc_info.value.status_code == 429
