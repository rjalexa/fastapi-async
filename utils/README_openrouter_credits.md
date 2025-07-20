# OpenRouter Credit Monitoring Utility

A comprehensive utility for monitoring OpenRouter API credit usage and sending alerts when credits are low.

## Features

- **Real-time Credit Monitoring**: Fetch current usage from OpenRouter API
- **Configurable Alerts**: Set warning and critical thresholds
- **Historical Tracking**: Store credit usage history in Redis
- **Alert Cooldown**: Prevent spam alerts with configurable cooldown periods
- **Multiple Commands**: Check, monitor, and view history
- **Redis Integration**: Store alerts and history for application integration

## Files

- `monitor_openrouter_credits.py` - Main monitoring utility with full Redis integration
- `test_openrouter_credits.py` - Simple test script without Redis dependency

## Configuration

The utility uses environment variables for configuration:

```bash
# Required
OPENROUTER_API_KEY=your_openrouter_api_key

# Optional (with defaults)
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
REDIS_URL=redis://localhost:6379/0
CREDIT_WARNING_THRESHOLD=10.0
CREDIT_CRITICAL_THRESHOLD=5.0
CREDIT_CHECK_INTERVAL_MINUTES=30
CREDIT_ALERT_COOLDOWN_HOURS=1
```

## Usage

### Basic Credit Check

```bash
# Single credit check
python3 utils/monitor_openrouter_credits.py check

# Or just run without arguments
python3 utils/monitor_openrouter_credits.py
```

### Continuous Monitoring

```bash
# Start continuous monitoring (checks every 30 minutes by default)
python3 utils/monitor_openrouter_credits.py monitor
```

### View Credit History

```bash
# View last 24 hours of credit history
python3 utils/monitor_openrouter_credits.py history

# View last 48 hours
python3 utils/monitor_openrouter_credits.py history 48
```

### Test API Connection

```bash
# Test OpenRouter API connection without Redis
python3 utils/test_openrouter_credits.py
```

## OpenRouter API Response

The utility works with the OpenRouter `/auth/key` endpoint which returns:

```json
{
  "data": {
    "label": "sk-or-v1-...",
    "limit": null,
    "usage": 292.0178864635,
    "is_provisioning_key": false,
    "limit_remaining": null,
    "is_free_tier": false,
    "rate_limit": {
      "requests": 230,
      "interval": "10s"
    }
  }
}
```

**Note**: The `usage` field represents total usage amount (not remaining balance). The utility currently uses this as a proxy for monitoring, but in a production environment, you would need to track the original balance separately to calculate remaining credits.

## Redis Data Structure

The utility stores data in Redis with the following keys:

### Current Status
- `openrouter:credits:current` - Hash with current credit information
- `openrouter:monitoring:status` - Hash with monitoring status

### Historical Data
- `openrouter:credits:history:{timestamp}` - Individual history entries
- `openrouter:credits:timeline` - Sorted set for time-based queries

### Alerts
- `openrouter:alerts:{timestamp}` - Individual alert records
- `openrouter:alerts:list` - List of recent alerts
- `openrouter:alerts:last:{type}` - Cooldown tracking

### Real-time Updates
- `openrouter-alerts` - Redis pub/sub channel for real-time alerts

## Alert Types

- **Warning**: Triggered when usage exceeds warning threshold
- **Critical**: Triggered when usage exceeds critical threshold

Alerts include cooldown periods to prevent spam and are stored in Redis for application integration.

## Integration with Main Application

The utility is designed to integrate with the main FastAPI application:

1. **Scheduled Monitoring**: Run as a cron job or background task
2. **Real-time Alerts**: Subscribe to Redis pub/sub channel `openrouter-alerts`
3. **Historical Data**: Query Redis for usage trends and history
4. **Status Dashboard**: Display current status from Redis data

## Example Cron Job

```bash
# Check credits every 30 minutes
*/30 * * * * cd /path/to/project && python3 utils/monitor_openrouter_credits.py check

# Or run continuous monitoring as a service
# python3 utils/monitor_openrouter_credits.py monitor
```

## Error Handling

The utility includes comprehensive error handling for:

- Network connectivity issues
- API authentication errors
- Redis connection problems
- Invalid API responses
- Configuration errors

## Dependencies

- `httpx` - HTTP client for API requests
- `redis` - Redis client for data storage
- `pydantic-settings` - Configuration management
- `pydantic` - Data validation

## Development

To extend the utility:

1. **Add New Alert Types**: Extend the alert system in `send_alert()`
2. **Custom Thresholds**: Add new threshold types in settings
3. **Additional Metrics**: Parse more fields from OpenRouter API response
4. **Integration**: Add webhook or email notification support

## Troubleshooting

### Common Issues

1. **Redis Connection Error**: Ensure Redis is running and accessible
2. **API Key Error**: Verify OPENROUTER_API_KEY is set correctly
3. **Permission Error**: Ensure script has read access to .env file

### Debug Mode

The utility includes debug output showing the raw API response. Remove or comment out the debug print statement in production:

```python
# Debug: Print the raw response to understand the structure
print(f"DEBUG: Raw OpenRouter API response: {json.dumps(data, indent=2)}")
```

## Security Considerations

- Store API keys securely (use environment variables, not hardcoded)
- Limit Redis access to authorized applications only
- Consider using Redis AUTH if running in production
- Monitor alert frequency to detect potential issues
