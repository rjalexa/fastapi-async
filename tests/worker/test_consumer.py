"""Tests for worker consumer functionality."""

import pytest
import signal
import sys
from unittest.mock import MagicMock, patch, call
import redis

from src.worker.consumer import signal_handler, main


class TestSignalHandler:
    """Test signal handler functionality."""

    @patch("sys.exit")
    @patch("src.worker.consumer.logger")
    def test_signal_handler_sigint(self, mock_logger, mock_exit):
        """Test signal handler with SIGINT."""
        signal_handler(signal.SIGINT, None)
        
        mock_logger.info.assert_called_with("Received signal 2, shutting down consumer...")
        mock_exit.assert_called_with(0)

    @patch("sys.exit")
    @patch("src.worker.consumer.logger")
    def test_signal_handler_sigterm(self, mock_logger, mock_exit):
        """Test signal handler with SIGTERM."""
        signal_handler(signal.SIGTERM, None)
        
        mock_logger.info.assert_called_with("Received signal 15, shutting down consumer...")
        mock_exit.assert_called_with(0)

    @patch("sys.exit")
    @patch("src.worker.consumer.logger")
    def test_signal_handler_custom_signal(self, mock_logger, mock_exit):
        """Test signal handler with custom signal number."""
        signal_handler(99, None)
        
        mock_logger.info.assert_called_with("Received signal 99, shutting down consumer...")
        mock_exit.assert_called_with(0)


class TestMainFunction:
    """Test main consumer function."""

    @patch("signal.signal")
    @patch("src.worker.consumer.logger")
    def test_main_signal_registration(self, mock_logger, mock_signal):
        """Test that main function registers signal handlers."""
        with patch("redis.from_url", side_effect=Exception("Stop test")), \
             patch("src.worker.consumer.settings"), \
             pytest.raises(Exception, match="Stop test"):
            
            main()
        
        # Verify signal handlers were registered
        expected_calls = [
            call(signal.SIGINT, signal_handler),
            call(signal.SIGTERM, signal_handler)
        ]
        mock_signal.assert_has_calls(expected_calls, any_order=True)

    @patch("signal.signal")
    @patch("src.worker.consumer.logger")
    @patch("redis.from_url")
    @patch("src.worker.consumer.settings")
    def test_main_redis_connection_setup(self, mock_settings, mock_redis_from_url, mock_logger, mock_signal):
        """Test Redis connection setup in main function."""
        mock_settings.redis_url = "redis://localhost:6379"
        mock_redis_conn = MagicMock()
        mock_redis_from_url.return_value = mock_redis_conn
        
        # Mock the infinite loop to exit after one iteration
        mock_redis_conn.llen.return_value = 0
        mock_redis_conn.blpop.return_value = None
        
        with patch("time.time", return_value=1000), \
             patch("time.sleep"), \
             patch("socket.gethostname", return_value="test-host"), \
             patch("os.getpid", return_value=12345), \
             patch("uuid.uuid4") as mock_uuid:
            
            mock_uuid.return_value = MagicMock()
            mock_uuid.return_value.__str__ = MagicMock(return_value="test-uuid-1234")
            
            # Run one iteration then raise KeyboardInterrupt to exit
            def side_effect(*args, **kwargs):
                raise KeyboardInterrupt("Test interrupt")
            
            mock_redis_conn.blpop.side_effect = side_effect
            
            main()
        
        # Verify Redis connection was created
        mock_redis_from_url.assert_called_with(mock_settings.redis_url, decode_responses=True)

    @patch("signal.signal")
    @patch("src.worker.consumer.logger")
    @patch("redis.from_url")
    @patch("src.worker.consumer.settings")
    def test_main_worker_id_generation(self, mock_settings, mock_redis_from_url, mock_logger, mock_signal):
        """Test worker ID generation in main function."""
        mock_settings.redis_url = "redis://localhost:6379"
        mock_redis_conn = MagicMock()
        mock_redis_from_url.return_value = mock_redis_conn
        
        with patch("time.time", return_value=1000), \
             patch("socket.gethostname", return_value="test-host"), \
             patch("os.getpid", return_value=12345), \
             patch("uuid.uuid4") as mock_uuid:
            
            mock_uuid.return_value = MagicMock()
            mock_uuid.return_value.__str__ = MagicMock(return_value="test-uuid-1234")
            
            # Mock to exit after setup
            def side_effect(*args, **kwargs):
                raise KeyboardInterrupt("Test interrupt")
            
            mock_redis_conn.blpop.side_effect = side_effect
            
            main()
        
        # Verify worker ID components were used
        mock_uuid.assert_called()

    @patch("signal.signal")
    @patch("src.worker.consumer.logger")
    @patch("redis.from_url")
    @patch("src.worker.consumer.settings")
    def test_main_heartbeat_update(self, mock_settings, mock_redis_from_url, mock_logger, mock_signal):
        """Test heartbeat update functionality."""
        mock_settings.redis_url = "redis://localhost:6379"
        mock_redis_conn = MagicMock()
        mock_redis_from_url.return_value = mock_redis_conn
        
        # Mock time to trigger heartbeat update
        time_values = [0, 35, 70]  # 35 seconds apart to trigger heartbeat
        
        with patch("time.time", side_effect=time_values), \
             patch("socket.gethostname", return_value="test-host"), \
             patch("os.getpid", return_value=12345), \
             patch("uuid.uuid4") as mock_uuid:
            
            mock_uuid.return_value = MagicMock()
            mock_uuid.return_value.__str__ = MagicMock(return_value="test-uuid-1234")
            
            # Mock to exit after a few iterations
            call_count = 0
            def blpop_side_effect(*args, **kwargs):
                nonlocal call_count
                call_count += 1
                if call_count >= 2:
                    raise KeyboardInterrupt("Test interrupt")
                return None
            
            mock_redis_conn.blpop.side_effect = blpop_side_effect
            mock_redis_conn.llen.return_value = 0
            
            main()
        
        # Verify heartbeat was set
        mock_redis_conn.setex.assert_called()

    @patch("signal.signal")
    @patch("src.worker.consumer.logger")
    @patch("redis.from_url")
    @patch("src.worker.consumer.settings")
    def test_main_task_processing(self, mock_settings, mock_redis_from_url, mock_logger, mock_signal):
        """Test task processing in main function."""
        mock_settings.redis_url = "redis://localhost:6379"
        mock_redis_conn = MagicMock()
        mock_redis_from_url.return_value = mock_redis_conn
        
        # Mock task retrieval
        mock_redis_conn.llen.return_value = 0
        mock_redis_conn.blpop.return_value = ("tasks:pending:primary", "test-task-123")
        
        with patch("time.time", return_value=1000), \
             patch("socket.gethostname", return_value="test-host"), \
             patch("os.getpid", return_value=12345), \
             patch("uuid.uuid4") as mock_uuid, \
             patch("src.worker.consumer.celery_app") as mock_celery_app:
            
            mock_uuid.return_value = MagicMock()
            mock_uuid.return_value.__str__ = MagicMock(return_value="test-uuid-1234")
            
            # Mock to exit after processing one task
            call_count = 0
            def blpop_side_effect(*args, **kwargs):
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    return ("tasks:pending:primary", "test-task-123")
                else:
                    raise KeyboardInterrupt("Test interrupt")
            
            mock_redis_conn.blpop.side_effect = blpop_side_effect
            
            main()
        
        # Verify task was dispatched
        mock_celery_app.send_task.assert_called_with("summarize_text", args=["test-task-123"])

    @patch("signal.signal")
    @patch("src.worker.consumer.logger")
    @patch("redis.from_url")
    @patch("src.worker.consumer.settings")
    def test_main_queue_priority_logic(self, mock_settings, mock_redis_from_url, mock_logger, mock_signal):
        """Test queue priority logic in main function."""
        mock_settings.redis_url = "redis://localhost:6379"
        mock_redis_conn = MagicMock()
        mock_redis_from_url.return_value = mock_redis_conn
        
        # Mock retry queue depth for adaptive ratio
        mock_redis_conn.llen.return_value = 5
        
        with patch("time.time", return_value=1000), \
             patch("socket.gethostname", return_value="test-host"), \
             patch("os.getpid", return_value=12345), \
             patch("uuid.uuid4") as mock_uuid, \
             patch("random.random", return_value=0.5), \
             patch("src.worker.consumer.calculate_adaptive_retry_ratio", return_value=0.3):
            
            mock_uuid.return_value = MagicMock()
            mock_uuid.return_value.__str__ = MagicMock(return_value="test-uuid-1234")
            
            # Mock to exit after setup
            def side_effect(*args, **kwargs):
                raise KeyboardInterrupt("Test interrupt")
            
            mock_redis_conn.blpop.side_effect = side_effect
            
            main()
        
        # Verify retry queue depth was checked
        mock_redis_conn.llen.assert_called_with("tasks:pending:retry")

    @patch("signal.signal")
    @patch("src.worker.consumer.logger")
    @patch("redis.from_url")
    @patch("src.worker.consumer.settings")
    def test_main_redis_error_handling(self, mock_settings, mock_redis_from_url, mock_logger, mock_signal):
        """Test Redis error handling in main function."""
        mock_settings.redis_url = "redis://localhost:6379"
        mock_redis_conn = MagicMock()
        mock_redis_from_url.return_value = mock_redis_conn
        
        with patch("time.time", return_value=1000), \
             patch("time.sleep") as mock_sleep, \
             patch("socket.gethostname", return_value="test-host"), \
             patch("os.getpid", return_value=12345), \
             patch("uuid.uuid4") as mock_uuid:
            
            mock_uuid.return_value = MagicMock()
            mock_uuid.return_value.__str__ = MagicMock(return_value="test-uuid-1234")
            
            # Mock Redis error then KeyboardInterrupt
            call_count = 0
            def blpop_side_effect(*args, **kwargs):
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    raise redis.RedisError("Connection failed")
                else:
                    raise KeyboardInterrupt("Test interrupt")
            
            mock_redis_conn.blpop.side_effect = blpop_side_effect
            mock_redis_conn.llen.return_value = 0
            
            main()
        
        # Verify error was logged and sleep was called
        mock_logger.error.assert_called()
        mock_sleep.assert_called_with(5)

    @patch("signal.signal")
    @patch("src.worker.consumer.logger")
    @patch("redis.from_url")
    @patch("src.worker.consumer.settings")
    def test_main_unexpected_error_handling(self, mock_settings, mock_redis_from_url, mock_logger, mock_signal):
        """Test unexpected error handling in main function."""
        mock_settings.redis_url = "redis://localhost:6379"
        mock_redis_conn = MagicMock()
        mock_redis_from_url.return_value = mock_redis_conn
        
        with patch("time.time", return_value=1000), \
             patch("time.sleep") as mock_sleep, \
             patch("socket.gethostname", return_value="test-host"), \
             patch("os.getpid", return_value=12345), \
             patch("uuid.uuid4") as mock_uuid:
            
            mock_uuid.return_value = MagicMock()
            mock_uuid.return_value.__str__ = MagicMock(return_value="test-uuid-1234")
            
            # Mock unexpected error then KeyboardInterrupt
            call_count = 0
            def blpop_side_effect(*args, **kwargs):
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    raise ValueError("Unexpected error")
                else:
                    raise KeyboardInterrupt("Test interrupt")
            
            mock_redis_conn.blpop.side_effect = blpop_side_effect
            mock_redis_conn.llen.return_value = 0
            
            main()
        
        # Verify error was logged and brief sleep was called
        mock_logger.error.assert_called()
        mock_sleep.assert_called_with(1)

    @patch("signal.signal")
    @patch("src.worker.consumer.logger")
    @patch("redis.from_url")
    @patch("src.worker.consumer.settings")
    def test_main_keyboard_interrupt_handling(self, mock_settings, mock_redis_from_url, mock_logger, mock_signal):
        """Test KeyboardInterrupt handling in main function."""
        mock_settings.redis_url = "redis://localhost:6379"
        mock_redis_conn = MagicMock()
        mock_redis_from_url.return_value = mock_redis_conn
        
        with patch("time.time", return_value=1000), \
             patch("socket.gethostname", return_value="test-host"), \
             patch("os.getpid", return_value=12345), \
             patch("uuid.uuid4") as mock_uuid:
            
            mock_uuid.return_value = MagicMock()
            mock_uuid.return_value.__str__ = MagicMock(return_value="test-uuid-1234")
            
            mock_redis_conn.blpop.side_effect = KeyboardInterrupt("User interrupt")
            
            main()
        
        # Verify interrupt was logged
        mock_logger.info.assert_called_with("Consumer interrupted by user")

    @patch("signal.signal")
    @patch("src.worker.consumer.logger")
    @patch("sys.exit")
    def test_main_startup_error_handling(self, mock_exit, mock_logger, mock_signal):
        """Test startup error handling in main function."""
        with patch("redis.from_url", side_effect=Exception("Startup failed")):
            main()
        
        # Verify error was logged and exit was called
        mock_logger.error.assert_called()
        mock_exit.assert_called_with(1)

    @patch("signal.signal")
    @patch("src.worker.consumer.logger")
    @patch("redis.from_url")
    @patch("src.worker.consumer.settings")
    def test_main_timeout_handling(self, mock_settings, mock_redis_from_url, mock_logger, mock_signal):
        """Test timeout handling in main function."""
        mock_settings.redis_url = "redis://localhost:6379"
        mock_redis_conn = MagicMock()
        mock_redis_from_url.return_value = mock_redis_conn
        
        with patch("time.time", return_value=1000), \
             patch("socket.gethostname", return_value="test-host"), \
             patch("os.getpid", return_value=12345), \
             patch("uuid.uuid4") as mock_uuid:
            
            mock_uuid.return_value = MagicMock()
            mock_uuid.return_value.__str__ = MagicMock(return_value="test-uuid-1234")
            
            # Mock timeout (None result) then KeyboardInterrupt
            call_count = 0
            def blpop_side_effect(*args, **kwargs):
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    return None  # Timeout
                else:
                    raise KeyboardInterrupt("Test interrupt")
            
            mock_redis_conn.blpop.side_effect = blpop_side_effect
            mock_redis_conn.llen.return_value = 0
            
            main()
        
        # Verify blpop was called with timeout
        mock_redis_conn.blpop.assert_called()
        args, kwargs = mock_redis_conn.blpop.call_args
        assert kwargs.get("timeout") == 5 or (len(args) > 1 and args[1] == 5)


class TestConsumerIntegration:
    """Test consumer integration scenarios."""

    @patch("signal.signal")
    @patch("src.worker.consumer.logger")
    @patch("redis.from_url")
    @patch("src.worker.consumer.settings")
    def test_full_consumer_workflow(self, mock_settings, mock_redis_from_url, mock_logger, mock_signal):
        """Test full consumer workflow with task processing."""
        mock_settings.redis_url = "redis://localhost:6379"
        mock_redis_conn = MagicMock()
        mock_redis_from_url.return_value = mock_redis_conn
        
        # Simulate processing multiple tasks
        tasks = [
            ("tasks:pending:primary", "task-1"),
            ("tasks:pending:retry", "task-2"),
            None,  # Timeout
        ]
        
        with patch("time.time", return_value=1000), \
             patch("socket.gethostname", return_value="test-host"), \
             patch("os.getpid", return_value=12345), \
             patch("uuid.uuid4") as mock_uuid, \
             patch("src.worker.consumer.celery_app") as mock_celery_app, \
             patch("random.random", return_value=0.5), \
             patch("src.worker.consumer.calculate_adaptive_retry_ratio", return_value=0.3):
            
            mock_uuid.return_value = MagicMock()
            mock_uuid.return_value.__str__ = MagicMock(return_value="test-uuid-1234")
            
            call_count = 0
            def blpop_side_effect(*args, **kwargs):
                nonlocal call_count
                if call_count < len(tasks):
                    result = tasks[call_count]
                    call_count += 1
                    return result
                else:
                    raise KeyboardInterrupt("Test interrupt")
            
            mock_redis_conn.blpop.side_effect = blpop_side_effect
            mock_redis_conn.llen.return_value = 2
            
            main()
        
        # Verify tasks were processed
        expected_calls = [
            call("summarize_text", args=["task-1"]),
            call("summarize_text", args=["task-2"])
        ]
        mock_celery_app.send_task.assert_has_calls(expected_calls)

    @patch("signal.signal")
    @patch("src.worker.consumer.logger")
    @patch("redis.from_url")
    @patch("src.worker.consumer.settings")
    def test_consumer_logging_integration(self, mock_settings, mock_redis_from_url, mock_logger, mock_signal):
        """Test consumer logging integration."""
        mock_settings.redis_url = "redis://localhost:6379"
        mock_redis_conn = MagicMock()
        mock_redis_from_url.return_value = mock_redis_conn
        
        with patch("time.time", return_value=1000), \
             patch("socket.gethostname", return_value="test-host"), \
             patch("os.getpid", return_value=12345), \
             patch("uuid.uuid4") as mock_uuid, \
             patch("src.worker.consumer.celery_app") as mock_celery_app:
            
            mock_uuid.return_value = MagicMock()
            mock_uuid.return_value.__str__ = MagicMock(return_value="test-uuid-1234")
            
            # Process one task then exit
            mock_redis_conn.blpop.side_effect = [
                ("tasks:pending:primary", "test-task"),
                KeyboardInterrupt("Test interrupt")
            ]
            mock_redis_conn.llen.return_value = 0
            
            main()
        
        # Verify startup and task processing were logged
        log_calls = [call[0][0] for call in mock_logger.info.call_args_list]
        assert any("Starting AsyncTaskFlow Redis Queue Consumer" in msg for msg in log_calls)
        assert any("Received task test-task" in msg for msg in log_calls)
        assert any("Dispatched task test-task" in msg for msg in log_calls)
