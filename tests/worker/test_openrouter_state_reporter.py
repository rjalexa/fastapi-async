import pytest
import asyncio
import os
import sys
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timezone

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from worker.openrouter_state_reporter import WorkerOpenRouterReporter


class TestWorkerOpenRouterReporter:
    """Test cases for the WorkerOpenRouterReporter class."""

    @pytest.fixture
    def mock_redis(self):
        """Create a mock Redis client."""
        mock = AsyncMock()
        mock.set.return_value = True
        mock.hgetall.return_value = {}
        mock.hset.return_value = True
        mock.delete.return_value = True
        mock.expire.return_value = True
        mock.hincrby.return_value = 1
        mock.lpush.return_value = 1
        mock.ltrim.return_value = True
        
        # Mock pipeline context manager
        pipeline_mock = AsyncMock()
        pipeline_mock.hincrby.return_value = None
        pipeline_mock.expire.return_value = None
        pipeline_mock.execute.return_value = [1, 1, 1, 1]
        mock.pipeline.return_value.__aenter__.return_value = pipeline_mock
        mock.pipeline.return_value.__aexit__.return_value = None
        
        return mock

    @pytest.fixture
    def state_reporter(self, mock_redis):
        """Create a WorkerOpenRouterReporter instance with mocked dependencies."""
        return WorkerOpenRouterReporter(redis_client=mock_redis)

    @pytest.mark.asyncio
    async def test_initialization(self, mock_redis):
        """Test WorkerOpenRouterReporter initialization."""
        reporter = WorkerOpenRouterReporter(redis_client=mock_redis)
        
        assert reporter.redis == mock_redis
        assert reporter._worker_id is None

    @pytest.mark.asyncio
    async def test_initialization_without_redis(self):
        """Test initialization without providing Redis client."""
        with patch('worker.openrouter_state_reporter.get_worker_standard_redis') as mock_get_redis:
            mock_redis = AsyncMock()
            mock_get_redis.return_value = mock_redis
            
            reporter = WorkerOpenRouterReporter()
            
            # Redis should be None initially
            assert reporter.redis is None

    @pytest.mark.asyncio
    async def test_get_worker_id_from_cgroup(self, state_reporter):
        """Test worker ID generation from cgroup (Docker container)."""
        mock_cgroup_content = """
12:memory:/docker/1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef
11:devices:/docker/1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef
"""
        
        with patch('builtins.open', mock_open_multiple_files({'/proc/self/cgroup': mock_cgroup_content})):
            worker_id = state_reporter._get_worker_id()
            
            assert worker_id.startswith("worker-")
            assert "1234567890ab" in worker_id

    @pytest.mark.asyncio
    async def test_get_worker_id_fallback(self, state_reporter):
        """Test worker ID generation fallback to hostname + PID."""
        with patch('builtins.open', side_effect=FileNotFoundError):
            with patch('os.uname') as mock_uname:
                with patch('os.getpid', return_value=12345):
                    mock_uname.return_value.nodename = "test-host"
                    
                    worker_id = state_reporter._get_worker_id()
                    
                    assert worker_id == "worker-test-host-12345"

    @pytest.mark.asyncio
    async def test_classify_error_by_status_code(self, state_reporter):
        """Test error classification by HTTP status code."""
        assert state_reporter._classify_error("Some error", 401) == "api_key_invalid"
        assert state_reporter._classify_error("Some error", 402) == "credits_exhausted"
        assert state_reporter._classify_error("Some error", 429) == "rate_limited"
        assert state_reporter._classify_error("Some error", 503) == "service_unavailable"

    @pytest.mark.asyncio
    async def test_classify_error_by_message(self, state_reporter):
        """Test error classification by error message content."""
        assert state_reporter._classify_error("Invalid API key", None) == "api_key_invalid"
        assert state_reporter._classify_error("Insufficient credits", None) == "credits_exhausted"
        assert state_reporter._classify_error("Rate limit exceeded", None) == "rate_limited"
        assert state_reporter._classify_error("Service unavailable", None) == "service_unavailable"
        assert state_reporter._classify_error("Connection timeout", None) == "timeout"
        assert state_reporter._classify_error("Network error", None) == "network_error"
        assert state_reporter._classify_error("Unknown issue", None) == "unknown_error"

    @pytest.mark.asyncio
    async def test_report_api_error_success(self, state_reporter, mock_redis):
        """Test successful API error reporting."""
        # Mock successful lock acquisition
        mock_redis.set.return_value = True
        
        result = await state_reporter.report_api_error(
            error_message="Rate limit exceeded",
            status_code=429,
            error_type="rate_limited"
        )
        
        assert result is True
        mock_redis.set.assert_called()  # Lock acquisition
        mock_redis.hset.assert_called()  # State update
        mock_redis.delete.assert_called()  # Lock release

    @pytest.mark.asyncio
    async def test_report_api_error_lock_failed(self, state_reporter, mock_redis):
        """Test API error reporting when lock acquisition fails."""
        # Mock failed lock acquisition
        mock_redis.set.return_value = False
        
        result = await state_reporter.report_api_error(
            error_message="Some error",
            status_code=500
        )
        
        assert result is False
        # Should still log the error even if lock fails
        mock_redis.lpush.assert_called()

    @pytest.mark.asyncio
    async def test_report_api_error_with_rate_limit(self, state_reporter, mock_redis):
        """Test API error reporting for rate limit errors."""
        mock_redis.set.return_value = True
        
        result = await state_reporter.report_api_error(
            error_message="Rate limit exceeded",
            status_code=429
        )
        
        assert result is True
        
        # Check that rate_limit_reset was set in the state
        call_args = mock_redis.hset.call_args
        state_data = call_args[1]['mapping']
        assert 'rate_limit_reset' in state_data

    @pytest.mark.asyncio
    async def test_report_api_success(self, state_reporter, mock_redis):
        """Test successful API success reporting."""
        mock_redis.set.return_value = True
        
        result = await state_reporter.report_api_success()
        
        assert result is True
        
        # Verify state was updated to active
        call_args = mock_redis.hset.call_args
        state_data = call_args[1]['mapping']
        assert state_data['state'] == 'active'
        assert state_data['consecutive_failures'] == '0'
        assert state_data['circuit_breaker_open'] == 'false'

    @pytest.mark.asyncio
    async def test_report_api_success_lock_failed(self, state_reporter, mock_redis):
        """Test API success reporting when lock acquisition fails."""
        mock_redis.set.return_value = False
        
        result = await state_reporter.report_api_success()
        
        assert result is False

    @pytest.mark.asyncio
    async def test_update_metrics_success(self, state_reporter, mock_redis):
        """Test metrics update for successful API call."""
        await state_reporter._update_metrics(mock_redis, "active", True)
        
        # Verify pipeline operations
        mock_redis.pipeline.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_metrics_failure(self, state_reporter, mock_redis):
        """Test metrics update for failed API call."""
        await state_reporter._update_metrics(mock_redis, "error", False)
        
        # Verify pipeline operations
        mock_redis.pipeline.assert_called_once()

    @pytest.mark.asyncio
    async def test_log_worker_error(self, state_reporter, mock_redis):
        """Test worker error logging."""
        await state_reporter._log_worker_error(
            mock_redis,
            "worker-123",
            "rate_limited",
            "Rate limit exceeded",
            429
        )
        
        mock_redis.lpush.assert_called_once()
        mock_redis.ltrim.assert_called_once()
        mock_redis.expire.assert_called_once()

    @pytest.mark.asyncio
    async def test_consecutive_failures_increment(self, state_reporter, mock_redis):
        """Test that consecutive failures are properly incremented."""
        # Mock existing state with some failures
        mock_redis.hgetall.return_value = {"consecutive_failures": "3"}
        mock_redis.set.return_value = True
        
        await state_reporter.report_api_error("API Error", 500)
        
        # Should increment to 4
        call_args = mock_redis.hset.call_args
        state_data = call_args[1]['mapping']
        assert state_data['consecutive_failures'] == '4'

    @pytest.mark.asyncio
    async def test_circuit_breaker_opens(self, state_reporter, mock_redis):
        """Test that circuit breaker opens after 5 consecutive failures."""
        # Mock existing state with 4 failures
        mock_redis.hgetall.return_value = {"consecutive_failures": "4"}
        mock_redis.set.return_value = True
        
        await state_reporter.report_api_error("API Error", 500)
        
        # Should open circuit breaker on 5th failure
        call_args = mock_redis.hset.call_args
        state_data = call_args[1]['mapping']
        assert state_data['consecutive_failures'] == '5'
        assert state_data['circuit_breaker_open'] == 'true'

    @pytest.mark.asyncio
    async def test_error_handling_in_report(self, state_reporter, mock_redis):
        """Test error handling during error reporting."""
        mock_redis.set.side_effect = Exception("Redis error")
        
        result = await state_reporter.report_api_error("Test error", 500)
        
        assert result is False

    @pytest.mark.asyncio
    async def test_convenience_functions(self, mock_redis):
        """Test convenience functions for error and success reporting."""
        with patch('worker.openrouter_state_reporter.get_openrouter_reporter') as mock_get_reporter:
            mock_reporter = AsyncMock()
            mock_reporter.report_api_error.return_value = True
            mock_reporter.report_api_success.return_value = True
            mock_get_reporter.return_value = mock_reporter
            
            from worker.openrouter_state_reporter import report_openrouter_error, report_openrouter_success
            
            # Test error reporting
            result = await report_openrouter_error("Test error", 500)
            assert result is True
            mock_reporter.report_api_error.assert_called_once_with("Test error", 500, None)
            
            # Test success reporting
            result = await report_openrouter_success()
            assert result is True
            mock_reporter.report_api_success.assert_called_once()

    @pytest.mark.asyncio
    async def test_redis_connection_fallback(self, state_reporter):
        """Test Redis connection fallback mechanism."""
        state_reporter.redis = None
        
        with patch('worker.openrouter_state_reporter.get_worker_standard_redis') as mock_get_redis:
            mock_redis = AsyncMock()
            mock_get_redis.side_effect = Exception("Connection failed")
            
            with patch('worker.openrouter_state_reporter.aioredis.from_url') as mock_from_url:
                mock_from_url.return_value = mock_redis
                
                redis_client = await state_reporter._get_redis()
                
                assert redis_client == mock_redis


def mock_open_multiple_files(files_dict):
    """Helper to mock opening multiple files with different content."""
    def mock_open_func(filename, *args, **kwargs):
        if filename in files_dict:
            from unittest.mock import mock_open
            return mock_open(read_data=files_dict[filename]).return_value
        else:
            raise FileNotFoundError(f"No such file: {filename}")
    
    return mock_open_func
