"""Tests for circuit breaker functionality."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch, mock_open
import httpx

from src.worker.circuit_breaker import (
    openrouter_breaker,
    calculate_backoff_delay,
    call_openrouter_api,
    get_container_id,
    get_circuit_breaker_status,
    reset_circuit_breaker,
    open_circuit_breaker,
)


class TestBackoffDelay:
    """Test exponential backoff delay calculation."""

    def test_calculate_backoff_delay_basic(self):
        """Test basic backoff delay calculation."""
        delay = calculate_backoff_delay(0)
        assert delay >= 1.0  # Base delay with jitter

    def test_calculate_backoff_delay_exponential(self):
        """Test exponential growth of backoff delay."""
        delay1 = calculate_backoff_delay(1, base_delay=1.0, max_delay=100.0)
        delay2 = calculate_backoff_delay(2, base_delay=1.0, max_delay=100.0)

        # Should grow exponentially (with jitter, so approximate)
        assert delay2 > delay1

    def test_calculate_backoff_delay_max_cap(self):
        """Test that backoff delay is capped at max_delay."""
        delay = calculate_backoff_delay(10, base_delay=1.0, max_delay=5.0)

        # Should be around max_delay (with jitter)
        assert delay <= 5.0 * 1.25  # Max delay + 25% jitter

    def test_calculate_backoff_delay_minimum(self):
        """Test that backoff delay respects minimum."""
        delay = calculate_backoff_delay(0, base_delay=2.0)

        # Should be at least base_delay
        assert delay >= 2.0

    def test_calculate_backoff_delay_jitter_variation(self):
        """Test that jitter creates variation in delays."""
        delays = []
        for _ in range(10):
            delay = calculate_backoff_delay(3, base_delay=1.0, max_delay=100.0)
            delays.append(delay)

        # Should have some variation due to jitter
        assert len(set(delays)) > 1


class TestContainerId:
    """Test container ID detection."""

    def test_get_container_id_from_cgroup_docker(self):
        """Test getting container ID from cgroup with docker format."""
        mock_cgroup_content = """
12:memory:/docker/1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef
11:cpu:/docker/1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef
"""

        with patch("builtins.open", mock_open(read_data=mock_cgroup_content)):
            container_id = get_container_id()
            assert container_id == "1234567890ab"  # First 12 chars

    def test_get_container_id_from_cgroup_systemd(self):
        """Test getting container ID from cgroup with systemd format."""
        mock_cgroup_content = """
12:memory:/system.slice/docker-abcdef123456.scope
"""

        with patch("builtins.open", mock_open(read_data=mock_cgroup_content)):
            container_id = get_container_id()
            assert container_id == "abcdef123456"

    def test_get_container_id_fallback_hostname(self):
        """Test fallback to hostname when cgroup fails."""
        with patch("builtins.open", side_effect=FileNotFoundError), patch(
            "os.uname"
        ) as mock_uname:
            mock_uname.return_value.nodename = "test-hostname-123"

            container_id = get_container_id()
            assert container_id == "test-hostname"  # First 12 chars

    def test_get_container_id_final_fallback(self):
        """Test final fallback when everything fails."""
        with patch("builtins.open", side_effect=FileNotFoundError), patch(
            "os.uname", side_effect=Exception("No uname")
        ):
            container_id = get_container_id()
            assert container_id == "unknown"


class TestCircuitBreakerStatus:
    """Test circuit breaker status functionality."""

    def test_get_circuit_breaker_status_basic(self):
        """Test getting basic circuit breaker status."""
        status = get_circuit_breaker_status()

        assert "state" in status
        assert "container_id" in status
        assert isinstance(status["state"], str)

    def test_get_circuit_breaker_status_with_counters(self):
        """Test circuit breaker status includes counters."""
        status = get_circuit_breaker_status()

        # Should have fail_count and success_count
        assert "fail_count" in status
        assert "success_count" in status
        assert isinstance(status["fail_count"], int)
        assert isinstance(status["success_count"], int)

    @patch("src.worker.circuit_breaker.openrouter_breaker")
    def test_get_circuit_breaker_status_error_handling(self, mock_breaker):
        """Test circuit breaker status error handling."""
        mock_breaker.current_state = None
        mock_breaker.side_effect = Exception("Test error")

        status = get_circuit_breaker_status()

        assert status["state"] == "error"
        assert "error" in status


class TestCircuitBreakerControl:
    """Test circuit breaker control functions."""

    def test_reset_circuit_breaker_success(self):
        """Test successful circuit breaker reset."""
        with patch.object(openrouter_breaker, "close") as mock_close:
            result = reset_circuit_breaker()

            assert result is True
            mock_close.assert_called_once()

    def test_reset_circuit_breaker_error(self):
        """Test circuit breaker reset error handling."""
        with patch.object(
            openrouter_breaker, "close", side_effect=Exception("Reset failed")
        ):
            with pytest.raises(Exception, match="Failed to reset circuit breaker"):
                reset_circuit_breaker()

    def test_open_circuit_breaker_success(self):
        """Test manually opening circuit breaker."""
        with patch.object(openrouter_breaker, "open") as mock_open:
            result = open_circuit_breaker()

            assert result is True
            mock_open.assert_called_once()


class TestCallOpenrouterApi:
    """Test OpenRouter API call functionality."""

    @pytest.mark.asyncio
    async def test_call_openrouter_api_success(self):
        """Test successful OpenRouter API call."""
        messages = [{"role": "user", "content": "Test message"}]

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "Test response"}}]
        }

        with patch(
            "src.worker.circuit_breaker.wait_for_rate_limit_token", return_value=True
        ), patch("httpx.AsyncClient") as mock_client_class, patch(
            "src.worker.circuit_breaker.report_openrouter_success"
        ) as mock_report_success:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.post.return_value = mock_response

            result = await call_openrouter_api(messages)

            assert result == "Test response"
            mock_report_success.assert_called_once()

    @pytest.mark.asyncio
    async def test_call_openrouter_api_rate_limit_timeout(self):
        """Test API call when rate limit token acquisition times out."""
        messages = [{"role": "user", "content": "Test message"}]

        with patch(
            "src.worker.circuit_breaker.wait_for_rate_limit_token", return_value=False
        ):
            with pytest.raises(Exception, match="Rate limit token acquisition timeout"):
                await call_openrouter_api(messages)

    @pytest.mark.asyncio
    async def test_call_openrouter_api_rate_limited(self):
        """Test API call handling rate limiting (429)."""
        messages = [{"role": "user", "content": "Test message"}]

        # First response is rate limited, second is successful
        mock_response_429 = MagicMock()
        mock_response_429.status_code = 429
        mock_response_429.headers = {"retry-after": "60"}

        mock_response_200 = MagicMock()
        mock_response_200.status_code = 200
        mock_response_200.json.return_value = {
            "choices": [{"message": {"content": "Success after retry"}}]
        }

        with patch(
            "src.worker.circuit_breaker.wait_for_rate_limit_token", return_value=True
        ), patch("httpx.AsyncClient") as mock_client_class, patch(
            "asyncio.sleep"
        ) as mock_sleep, patch(
            "src.worker.circuit_breaker.report_openrouter_error"
        ) as mock_report_error, patch(
            "src.worker.circuit_breaker.report_openrouter_success"
        ) as mock_report_success:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.post.side_effect = [mock_response_429, mock_response_200]

            result = await call_openrouter_api(messages)

            assert result == "Success after retry"
            mock_sleep.assert_called()  # Should have slept due to rate limiting
            mock_report_error.assert_called()
            mock_report_success.assert_called()

    @pytest.mark.asyncio
    async def test_call_openrouter_api_http_error(self):
        """Test API call with HTTP error."""
        messages = [{"role": "user", "content": "Test message"}]

        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"

        with patch(
            "src.worker.circuit_breaker.wait_for_rate_limit_token", return_value=True
        ), patch("httpx.AsyncClient") as mock_client_class, patch(
            "src.worker.circuit_breaker.report_openrouter_error"
        ) as mock_report_error:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.post.return_value = mock_response

            with pytest.raises(Exception, match="OpenRouter API error: 500"):
                await call_openrouter_api(messages)

            mock_report_error.assert_called()

    @pytest.mark.asyncio
    async def test_call_openrouter_api_timeout(self):
        """Test API call with timeout."""
        messages = [{"role": "user", "content": "Test message"}]

        with patch(
            "src.worker.circuit_breaker.wait_for_rate_limit_token", return_value=True
        ), patch("httpx.AsyncClient") as mock_client_class, patch(
            "asyncio.sleep"
        ), patch(
            "src.worker.circuit_breaker.report_openrouter_error"
        ) as mock_report_error:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.post.side_effect = httpx.TimeoutException("Request timeout")

            with pytest.raises(Exception, match="OpenRouter API timeout"):
                await call_openrouter_api(messages)

            mock_report_error.assert_called()

    @pytest.mark.asyncio
    async def test_call_openrouter_api_network_error(self):
        """Test API call with network error."""
        messages = [{"role": "user", "content": "Test message"}]

        with patch(
            "src.worker.circuit_breaker.wait_for_rate_limit_token", return_value=True
        ), patch("httpx.AsyncClient") as mock_client_class, patch(
            "src.worker.circuit_breaker.report_openrouter_error"
        ) as mock_report_error:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.post.side_effect = httpx.RequestError("Network error")

            with pytest.raises(Exception, match="OpenRouter API request error"):
                await call_openrouter_api(messages)

            mock_report_error.assert_called()

    @pytest.mark.asyncio
    async def test_call_openrouter_api_specific_error_codes(self):
        """Test API call with specific error codes."""
        messages = [{"role": "user", "content": "Test message"}]

        test_cases = [
            (401, "api_key_invalid"),
            (402, "credits_exhausted"),
            (503, "service_unavailable"),
        ]

        for status_code, expected_error_type in test_cases:
            mock_response = MagicMock()
            mock_response.status_code = status_code
            mock_response.text = f"Error {status_code}"

            with patch(
                "src.worker.circuit_breaker.wait_for_rate_limit_token",
                return_value=True,
            ), patch("httpx.AsyncClient") as mock_client_class, patch(
                "src.worker.circuit_breaker.report_openrouter_error"
            ) as mock_report_error:
                mock_client = AsyncMock()
                mock_client_class.return_value.__aenter__.return_value = mock_client
                mock_client.post.return_value = mock_response

                with pytest.raises(Exception):
                    await call_openrouter_api(messages)

                # Verify the error was reported with correct error type
                mock_report_error.assert_called()
                call_args = mock_report_error.call_args[1]
                assert call_args["error_type"] == expected_error_type


class TestCircuitBreakerIntegration:
    """Test circuit breaker integration."""

    def test_openrouter_breaker_configuration(self):
        """Test that openrouter_breaker is properly configured."""
        assert openrouter_breaker.fail_max == 10
        assert openrouter_breaker.reset_timeout == 120
        assert KeyboardInterrupt in openrouter_breaker.excluded_exceptions

    @pytest.mark.asyncio
    async def test_circuit_breaker_with_api_call(self):
        """Test circuit breaker behavior with API calls."""
        messages = [{"role": "user", "content": "Test message"}]

        # Mock a failing response
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Server Error"

        with patch(
            "src.worker.circuit_breaker.wait_for_rate_limit_token", return_value=True
        ), patch("httpx.AsyncClient") as mock_client_class, patch(
            "src.worker.circuit_breaker.report_openrouter_error"
        ):
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.post.return_value = mock_response

            # Should raise exception due to 500 error
            with pytest.raises(Exception):
                await call_openrouter_api(messages)

    def test_circuit_breaker_status_integration(self):
        """Test circuit breaker status integration."""
        # Reset breaker to known state
        try:
            reset_circuit_breaker()
        except Exception:
            pass

        status = get_circuit_breaker_status()

        # Should have basic status information
        assert "state" in status
        assert "container_id" in status
        assert isinstance(status, dict)


class TestErrorReporting:
    """Test error reporting integration."""

    @pytest.mark.asyncio
    async def test_error_reporting_integration(self):
        """Test that errors are properly reported."""
        messages = [{"role": "user", "content": "Test message"}]

        with patch(
            "src.worker.circuit_breaker.wait_for_rate_limit_token", return_value=True
        ), patch("httpx.AsyncClient") as mock_client_class, patch(
            "src.worker.circuit_breaker.report_openrouter_error"
        ) as mock_report_error:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.post.side_effect = httpx.TimeoutException("Timeout")

            with pytest.raises(Exception):
                await call_openrouter_api(messages)

            # Verify error reporting was called
            mock_report_error.assert_called()

    @pytest.mark.asyncio
    async def test_success_reporting_integration(self):
        """Test that successes are properly reported."""
        messages = [{"role": "user", "content": "Test message"}]

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "Success"}}]
        }

        with patch(
            "src.worker.circuit_breaker.wait_for_rate_limit_token", return_value=True
        ), patch("httpx.AsyncClient") as mock_client_class, patch(
            "src.worker.circuit_breaker.report_openrouter_success"
        ) as mock_report_success:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.post.return_value = mock_response

            result = await call_openrouter_api(messages)

            assert result == "Success"
            mock_report_success.assert_called_once()
