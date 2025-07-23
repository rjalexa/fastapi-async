"""Tests for worker utility and helper functions."""

from unittest.mock import patch
from src.worker.tasks import (
    classify_error,
    calculate_retry_delay,
    calculate_adaptive_retry_ratio,
)


class TestClassifyError:
    """Test the classify_error function."""

    def test_dependency_errors(self):
        """Test that dependency errors are correctly classified."""
        dependency_patterns = [
            "poppler installed and in path",  # Fixed case to match source
            "command not found",
            "no such file or directory",
            "permission denied",
            "module not found",
            "import error",
            "library not found",
            "missing dependency",
            "environment variable not set",
            "configuration error",
            "invalid configuration",
            "database connection failed",
            "redis connection failed",
        ]

        for pattern in dependency_patterns:
            result = classify_error(0, pattern)
            assert (
                result == "DependencyError"
            ), f"Pattern '{pattern}' should be classified as DependencyError"

            # Test case insensitive matching
            result = classify_error(0, pattern.upper())
            assert (
                result == "DependencyError"
            ), f"Pattern '{pattern.upper()}' should be classified as DependencyError"

    def test_permanent_error_patterns(self):
        """Test that permanent error patterns are correctly classified."""
        permanent_patterns = [
            "invalid api key",
            "authentication failed",
            "unauthorized",
            "forbidden",
            "not found",
            "bad request",
            "invalid request",
            "malformed",
            "syntax error",
            "parse error",
            "invalid json",
            "invalid format",
            "unsupported format",
            "file too large",
            "quota exceeded",
            "limit exceeded",
        ]

        for pattern in permanent_patterns:
            result = classify_error(0, pattern)
            assert (
                result == "PermanentError"
            ), f"Pattern '{pattern}' should be classified as PermanentError"

    def test_http_status_code_classifications(self):
        """Test that HTTP status codes are correctly classified."""
        # Test permanent error status codes
        permanent_codes = [400, 401, 403, 404]
        for code in permanent_codes:
            result = classify_error(code, "some error message")
            assert (
                result == "PermanentError"
            ), f"Status code {code} should be classified as PermanentError"

        # Test insufficient credits
        result = classify_error(402, "some error message")
        assert result == "InsufficientCredits"

        # Test rate limit error
        result = classify_error(429, "some error message")
        assert result == "RateLimitError"

        # Test service unavailable
        result = classify_error(503, "some error message")
        assert result == "ServiceUnavailable"

        # Test other transient errors
        transient_codes = [500]
        for code in transient_codes:
            result = classify_error(code, "some error message")
            assert (
                result == "NetworkTimeout"
            ), f"Status code {code} should be classified as NetworkTimeout"

    def test_default_fallback(self):
        """Test that unknown errors fall back to Default classification."""
        result = classify_error(0, "some unknown error")
        assert result == "Default"

        result = classify_error(418, "I'm a teapot")  # Unusual status code
        assert result == "Default"


class TestCalculateRetryDelay:
    """Test the calculate_retry_delay function."""

    def test_insufficient_credits_schedule(self):
        """Test retry delays for insufficient credits."""
        expected_schedule = [300, 600, 1800]  # 5min, 10min, 30min

        for retry_count, expected_base in enumerate(expected_schedule):
            delay = calculate_retry_delay(retry_count, "InsufficientCredits")
            # Should be base delay + jitter (0-10% of base)
            assert expected_base <= delay <= expected_base * 1.1

        # Test beyond schedule length - should use last value
        delay = calculate_retry_delay(10, "InsufficientCredits")
        assert 1800 <= delay <= 1800 * 1.1

    def test_rate_limit_schedule(self):
        """Test retry delays for rate limit errors."""
        expected_schedule = [120, 300, 600, 1200]  # 2min, 5min, 10min, 20min

        for retry_count, expected_base in enumerate(expected_schedule):
            delay = calculate_retry_delay(retry_count, "RateLimitError")
            assert expected_base <= delay <= expected_base * 1.1

    def test_service_unavailable_schedule(self):
        """Test retry delays for service unavailable errors."""
        expected_schedule = [5, 10, 30, 60, 120]

        for retry_count, expected_base in enumerate(expected_schedule):
            delay = calculate_retry_delay(retry_count, "ServiceUnavailable")
            assert expected_base <= delay <= expected_base * 1.1

    def test_network_timeout_schedule(self):
        """Test retry delays for network timeout errors."""
        expected_schedule = [2, 5, 10, 30, 60]

        for retry_count, expected_base in enumerate(expected_schedule):
            delay = calculate_retry_delay(retry_count, "NetworkTimeout")
            assert expected_base <= delay <= expected_base * 1.1

    def test_default_schedule(self):
        """Test retry delays for default error type."""
        expected_schedule = [5, 15, 60, 300]

        for retry_count, expected_base in enumerate(expected_schedule):
            delay = calculate_retry_delay(retry_count, "Default")
            assert expected_base <= delay <= expected_base * 1.1

    def test_unknown_error_type_uses_default(self):
        """Test that unknown error types use the default schedule."""
        delay = calculate_retry_delay(0, "UnknownErrorType")
        assert 5 <= delay <= 5.5  # Base 5 + 10% jitter

    def test_jitter_randomness(self):
        """Test that jitter adds randomness to delays."""
        delays = []
        for _ in range(10):
            delay = calculate_retry_delay(0, "Default")
            delays.append(delay)

        # All delays should be different due to jitter
        assert len(set(delays)) > 1, "Jitter should make delays different"

        # All delays should be within expected range
        for delay in delays:
            assert 5 <= delay <= 5.5


class TestCalculateAdaptiveRetryRatio:
    """Test the calculate_adaptive_retry_ratio function."""

    @patch("src.worker.tasks.settings")
    def test_normal_queue_depth(self, mock_settings):
        """Test retry ratio when queue depth is normal."""
        mock_settings.retry_queue_warning = 100
        mock_settings.retry_queue_critical = 500
        mock_settings.default_retry_ratio = 0.3

        # Test below warning threshold
        ratio = calculate_adaptive_retry_ratio(50)
        assert ratio == 0.3

        ratio = calculate_adaptive_retry_ratio(99)
        assert ratio == 0.3

    @patch("src.worker.tasks.settings")
    def test_warning_queue_depth(self, mock_settings):
        """Test retry ratio when queue depth is at warning level."""
        mock_settings.retry_queue_warning = 100
        mock_settings.retry_queue_critical = 500
        mock_settings.default_retry_ratio = 0.3

        # Test at warning threshold
        ratio = calculate_adaptive_retry_ratio(100)
        assert ratio == 0.2

        ratio = calculate_adaptive_retry_ratio(300)
        assert ratio == 0.2

        ratio = calculate_adaptive_retry_ratio(499)
        assert ratio == 0.2

    @patch("src.worker.tasks.settings")
    def test_critical_queue_depth(self, mock_settings):
        """Test retry ratio when queue depth is at critical level."""
        mock_settings.retry_queue_warning = 100
        mock_settings.retry_queue_critical = 500
        mock_settings.default_retry_ratio = 0.3

        # Test at critical threshold
        ratio = calculate_adaptive_retry_ratio(500)
        assert ratio == 0.1

        ratio = calculate_adaptive_retry_ratio(1000)
        assert ratio == 0.1

    @patch("src.worker.tasks.settings")
    def test_edge_cases(self, mock_settings):
        """Test edge cases for queue depth."""
        mock_settings.retry_queue_warning = 100
        mock_settings.retry_queue_critical = 500
        mock_settings.default_retry_ratio = 0.3

        # Test zero depth
        ratio = calculate_adaptive_retry_ratio(0)
        assert ratio == 0.3

        # Test exactly at thresholds
        ratio = calculate_adaptive_retry_ratio(100)
        assert ratio == 0.2

        ratio = calculate_adaptive_retry_ratio(500)
        assert ratio == 0.1
