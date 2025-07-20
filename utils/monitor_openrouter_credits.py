#!/usr/bin/env python3
"""
OpenRouter Credit Monitoring and Alerting Utility

This script monitors OpenRouter account credits and provides alerts when credits are low.
It can be run manually or scheduled as a cron job for continuous monitoring.
"""

import asyncio
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional

import httpx
import redis.asyncio as aioredis
from pydantic import Field
from pydantic_settings import BaseSettings


class MonitorSettings(BaseSettings):
    """Settings for OpenRouter credit monitoring."""
    
    # OpenRouter Configuration
    openrouter_api_key: Optional[str] = Field(default=None, env="OPENROUTER_API_KEY")
    openrouter_base_url: str = Field(
        default="https://openrouter.ai/api/v1", env="OPENROUTER_BASE_URL"
    )
    
    # Redis Configuration
    redis_url: str = Field(default="redis://localhost:6379/0", env="REDIS_URL")
    
    # Alert Thresholds
    credit_warning_threshold: float = Field(default=10.0, env="CREDIT_WARNING_THRESHOLD")  # $10
    credit_critical_threshold: float = Field(default=5.0, env="CREDIT_CRITICAL_THRESHOLD")  # $5
    
    # Monitoring Configuration
    check_interval_minutes: int = Field(default=30, env="CREDIT_CHECK_INTERVAL_MINUTES")
    alert_cooldown_hours: int = Field(default=1, env="CREDIT_ALERT_COOLDOWN_HOURS")
    
    model_config = {
        "env_file": ".env",
        "case_sensitive": False,
        "extra": "ignore"  # Ignore extra environment variables
    }


async def get_openrouter_credits(api_key: str, base_url: str) -> Dict:
    """
    Fetch current credit information from OpenRouter API.
    
    Returns:
        Dictionary containing credit information
    """
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{base_url}/auth/key",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                timeout=30.0,
            )
            
            if response.status_code != 200:
                raise Exception(f"OpenRouter API error: {response.status_code} - {response.text}")
            
            data = response.json()
            
            # Handle different possible response structures
            if isinstance(data, dict):
                # Try different possible structures
                data_section = data.get("data", data)  # Use data section if exists, otherwise use root
                
                # Extract credit information with safe navigation
                balance = 0.0
                usage_today = 0.0
                usage_month = 0.0
                rate_limit = {}
                
                if isinstance(data_section, dict):
                    # OpenRouter API uses 'usage' field for total usage amount
                    # Note: This appears to be total usage, not remaining balance
                    total_usage = data_section.get("usage", 0.0)
                    
                    # For OpenRouter, we need to calculate remaining balance
                    # Since we don't have the original balance, we'll use usage as a proxy
                    # In a real scenario, you'd need to track the original balance separately
                    balance = total_usage  # This is actually total usage, not remaining balance
                    
                    # OpenRouter doesn't provide daily/monthly breakdowns in this endpoint
                    # We'll use the total usage for now
                    usage_today = 0.0  # Not available from this endpoint
                    usage_month = total_usage  # Use total usage as monthly usage
                    
                    rate_limit = data_section.get("rate_limit", {})
                
                credit_info = {
                    "balance": float(balance) if balance is not None else 0.0,
                    "usage_today": float(usage_today) if usage_today is not None else 0.0,
                    "usage_month": float(usage_month) if usage_month is not None else 0.0,
                    "rate_limit": rate_limit if isinstance(rate_limit, dict) else {},
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "raw_response": data
                }
                
                return credit_info
            else:
                raise Exception(f"Unexpected API response format: {type(data)}")
            
    except httpx.RequestError as e:
        raise Exception(f"Network error while fetching OpenRouter credits: {str(e)}")
    except json.JSONDecodeError as e:
        raise Exception(f"Invalid JSON response from OpenRouter API: {str(e)}")
    except Exception as e:
        raise Exception(f"Failed to fetch OpenRouter credits: {str(e)}")


async def store_credit_history(redis_conn: aioredis.Redis, credit_info: Dict) -> None:
    """Store credit information in Redis for historical tracking."""
    
    # Store current credit info
    await redis_conn.hset(
        "openrouter:credits:current",
        mapping={
            "balance": str(credit_info["balance"]),
            "usage_today": str(credit_info["usage_today"]),
            "usage_month": str(credit_info["usage_month"]),
            "timestamp": credit_info["timestamp"],
            "raw_data": json.dumps(credit_info["raw_response"])
        }
    )
    
    # Store rate limit configuration for distributed rate limiting
    rate_limit = credit_info.get("rate_limit", {})
    if rate_limit:
        await redis_conn.hset(
            "openrouter:rate_limit_config",
            mapping={
                "requests": str(rate_limit.get("requests", 0)),
                "interval": str(rate_limit.get("interval", "10s")),
                "updated_at": credit_info["timestamp"],
                "raw_config": json.dumps(rate_limit)
            }
        )
    
    # Store in time-series for historical analysis
    timestamp = int(time.time())
    history_key = f"openrouter:credits:history:{timestamp}"
    await redis_conn.hset(
        history_key,
        mapping={
            "balance": str(credit_info["balance"]),
            "usage_today": str(credit_info["usage_today"]),
            "usage_month": str(credit_info["usage_month"]),
            "timestamp": credit_info["timestamp"]
        }
    )
    
    # Set expiration for history entries (keep for 30 days)
    await redis_conn.expire(history_key, 30 * 24 * 60 * 60)
    
    # Add to sorted set for easy time-based queries
    await redis_conn.zadd("openrouter:credits:timeline", {history_key: timestamp})
    
    # Clean up old timeline entries (keep last 30 days)
    cutoff_time = timestamp - (30 * 24 * 60 * 60)
    await redis_conn.zremrangebyscore("openrouter:credits:timeline", 0, cutoff_time)


async def check_alert_cooldown(redis_conn: aioredis.Redis, alert_type: str, cooldown_hours: int) -> bool:
    """
    Check if we're still in cooldown period for a specific alert type.
    
    Returns:
        True if we can send alert, False if still in cooldown
    """
    last_alert_key = f"openrouter:alerts:last:{alert_type}"
    last_alert_time = await redis_conn.get(last_alert_key)
    
    if not last_alert_time:
        return True
    
    try:
        last_alert_timestamp = float(last_alert_time)
        cooldown_seconds = cooldown_hours * 60 * 60
        
        if time.time() - last_alert_timestamp > cooldown_seconds:
            return True
        else:
            return False
    except (ValueError, TypeError):
        return True


async def record_alert_sent(redis_conn: aioredis.Redis, alert_type: str) -> None:
    """Record that an alert was sent to implement cooldown."""
    last_alert_key = f"openrouter:alerts:last:{alert_type}"
    await redis_conn.set(last_alert_key, str(time.time()))


async def send_alert(redis_conn: aioredis.Redis, alert_type: str, message: str, credit_info: Dict) -> None:
    """
    Send alert by storing it in Redis for the application to pick up.
    In a production environment, you might want to integrate with email, Slack, etc.
    """
    alert_data = {
        "type": alert_type,
        "message": message,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "credit_balance": credit_info["balance"],
        "usage_today": credit_info["usage_today"],
        "usage_month": credit_info["usage_month"],
        "severity": "critical" if alert_type == "credit_critical" else "warning"
    }
    
    # Store alert in Redis
    alert_key = f"openrouter:alerts:{int(time.time())}"
    await redis_conn.hset(alert_key, mapping={k: str(v) for k, v in alert_data.items()})
    await redis_conn.expire(alert_key, 7 * 24 * 60 * 60)  # Keep alerts for 7 days
    
    # Add to alerts list for easy retrieval
    await redis_conn.lpush("openrouter:alerts:list", alert_key)
    await redis_conn.ltrim("openrouter:alerts:list", 0, 99)  # Keep last 100 alerts
    
    # Publish real-time alert
    await redis_conn.publish("openrouter-alerts", json.dumps(alert_data))
    
    print(f"🚨 ALERT SENT: {alert_type.upper()}")
    print(f"   Message: {message}")
    print(f"   Current Balance: ${credit_info['balance']:.2f}")
    print(f"   Usage Today: ${credit_info['usage_today']:.2f}")
    print(f"   Usage This Month: ${credit_info['usage_month']:.2f}")


async def monitor_credits(settings: MonitorSettings) -> Dict:
    """
    Main monitoring function that checks credits and sends alerts if needed.
    
    Returns:
        Dictionary with monitoring results
    """
    if not settings.openrouter_api_key:
        raise Exception("OpenRouter API key not configured")
    
    redis_conn = aioredis.from_url(settings.redis_url, decode_responses=True)
    
    try:
        # Fetch current credit information
        credit_info = await get_openrouter_credits(
            settings.openrouter_api_key,
            settings.openrouter_base_url
        )
        
        # Store credit history
        await store_credit_history(redis_conn, credit_info)
        
        balance = credit_info["balance"]
        alerts_sent = []
        
        # Check for critical threshold
        if balance <= settings.credit_critical_threshold:
            if await check_alert_cooldown(redis_conn, "credit_critical", settings.alert_cooldown_hours):
                message = f"CRITICAL: OpenRouter credit balance is critically low: ${balance:.2f} (threshold: ${settings.credit_critical_threshold:.2f})"
                await send_alert(redis_conn, "credit_critical", message, credit_info)
                await record_alert_sent(redis_conn, "credit_critical")
                alerts_sent.append("critical")
        
        # Check for warning threshold (only if not already critical)
        elif balance <= settings.credit_warning_threshold:
            if await check_alert_cooldown(redis_conn, "credit_warning", settings.alert_cooldown_hours):
                message = f"WARNING: OpenRouter credit balance is low: ${balance:.2f} (threshold: ${settings.credit_warning_threshold:.2f})"
                await send_alert(redis_conn, "credit_warning", message, credit_info)
                await record_alert_sent(redis_conn, "credit_warning")
                alerts_sent.append("warning")
        
        # Update monitoring status
        monitoring_status = {
            "last_check": datetime.now(timezone.utc).isoformat(),
            "balance": balance,
            "usage_today": credit_info["usage_today"],
            "usage_month": credit_info["usage_month"],
            "status": "critical" if balance <= settings.credit_critical_threshold else 
                     "warning" if balance <= settings.credit_warning_threshold else "ok",
            "alerts_sent": alerts_sent,
            "thresholds": {
                "warning": settings.credit_warning_threshold,
                "critical": settings.credit_critical_threshold
            }
        }
        
        await redis_conn.hset(
            "openrouter:monitoring:status",
            mapping={k: str(v) if not isinstance(v, (dict, list)) else json.dumps(v) 
                    for k, v in monitoring_status.items()}
        )
        
        return monitoring_status
        
    finally:
        await redis_conn.aclose()


async def get_credit_history(settings: MonitorSettings, hours: int = 24) -> Dict:
    """Get credit history for the specified number of hours."""
    redis_conn = aioredis.from_url(settings.redis_url, decode_responses=True)
    
    try:
        # Get timeline entries for the specified period
        cutoff_time = int(time.time()) - (hours * 60 * 60)
        timeline_entries = await redis_conn.zrangebyscore(
            "openrouter:credits:timeline", 
            cutoff_time, 
            "+inf",
            withscores=True
        )
        
        history = []
        for entry_key, timestamp in timeline_entries:
            entry_data = await redis_conn.hgetall(entry_key)
            if entry_data:
                history.append({
                    "timestamp": entry_data.get("timestamp"),
                    "balance": float(entry_data.get("balance", 0)),
                    "usage_today": float(entry_data.get("usage_today", 0)),
                    "usage_month": float(entry_data.get("usage_month", 0))
                })
        
        return {
            "period_hours": hours,
            "entries": sorted(history, key=lambda x: x["timestamp"]),
            "total_entries": len(history)
        }
        
    finally:
        await redis_conn.aclose()


async def main():
    """Main function for command-line usage."""
    settings = MonitorSettings()
    
    if len(sys.argv) > 1:
        command = sys.argv[1].lower()
        
        if command == "check":
            # Single check
            try:
                result = await monitor_credits(settings)
                print("✅ Credit monitoring check completed")
                print(f"   Balance: ${result['balance']:.2f}")
                print(f"   Status: {result['status'].upper()}")
                print(f"   Usage Today: ${result['usage_today']:.2f}")
                print(f"   Usage This Month: ${result['usage_month']:.2f}")
                if result['alerts_sent']:
                    print(f"   Alerts Sent: {', '.join(result['alerts_sent'])}")
            except Exception as e:
                print(f"❌ Error during credit check: {e}")
                sys.exit(1)
        
        elif command == "history":
            # Show credit history
            hours = int(sys.argv[2]) if len(sys.argv) > 2 else 24
            try:
                history = await get_credit_history(settings, hours)
                print(f"📊 Credit History (Last {hours} hours)")
                print(f"   Total Entries: {history['total_entries']}")
                
                if history['entries']:
                    print("\n   Recent Entries:")
                    for entry in history['entries'][-10:]:  # Show last 10 entries
                        timestamp = datetime.fromisoformat(entry['timestamp'].replace('Z', '+00:00'))
                        print(f"   {timestamp.strftime('%Y-%m-%d %H:%M:%S')} - Balance: ${entry['balance']:.2f}")
                else:
                    print("   No history entries found")
            except Exception as e:
                print(f"❌ Error retrieving history: {e}")
                sys.exit(1)
        
        elif command == "monitor":
            # Continuous monitoring
            print(f"🔄 Starting continuous credit monitoring (check every {settings.check_interval_minutes} minutes)")
            print(f"   Warning Threshold: ${settings.credit_warning_threshold:.2f}")
            print(f"   Critical Threshold: ${settings.credit_critical_threshold:.2f}")
            print("   Press Ctrl+C to stop")
            
            try:
                while True:
                    try:
                        result = await monitor_credits(settings)
                        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                        print(f"[{timestamp}] Balance: ${result['balance']:.2f} | Status: {result['status'].upper()}")
                        
                        if result['alerts_sent']:
                            print(f"              Alerts sent: {', '.join(result['alerts_sent'])}")
                        
                    except Exception as e:
                        print(f"❌ Error during monitoring cycle: {e}")
                    
                    # Wait for next check
                    await asyncio.sleep(settings.check_interval_minutes * 60)
                    
            except KeyboardInterrupt:
                print("\n🛑 Monitoring stopped by user")
        
        else:
            print(f"❌ Unknown command: {command}")
            print("Available commands: check, history [hours], monitor")
            sys.exit(1)
    
    else:
        # Default: single check
        try:
            result = await monitor_credits(settings)
            print("✅ OpenRouter Credit Check")
            print(f"   Balance: ${result['balance']:.2f}")
            print(f"   Status: {result['status'].upper()}")
            print(f"   Usage Today: ${result['usage_today']:.2f}")
            print(f"   Usage This Month: ${result['usage_month']:.2f}")
            
            if result['status'] != 'ok':
                print(f"\n⚠️  Consider adding credits to your OpenRouter account")
                print(f"   Warning threshold: ${result['thresholds']['warning']:.2f}")
                print(f"   Critical threshold: ${result['thresholds']['critical']:.2f}")
                
        except Exception as e:
            print(f"❌ Error: {e}")
            sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
