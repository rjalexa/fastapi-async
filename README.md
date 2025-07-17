# AsyncTaskFlow

A production-ready distributed task processing system built with FastAPI, Redis, and Celery. Implements robust architecture for handling long-running text summarization tasks via OpenRouter API, featuring comprehensive error handling, circuit breaker patterns, retry mechanisms, and dead letter queue management.

## 🚀 Quick Start

```bash
# Clone the repository
git clone <repository-url>
cd fastapi-async

# Copy environment configuration
cp .env.example .env

# Start all services
docker compose up -d

# View logs
docker compose logs -f
```

The application will be available at:
- Frontend: http://localhost:3000
- API: http://localhost:8000
- API Documentation: http://localhost:8000/docs

## 🏗️ Architecture

### System Components

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│                 │     │                 │     │                 │
│  Web Frontend   │────▶│   FastAPI App   │────▶│  Redis Broker   │
│  (TypeScript)   │     │   (REST API)    │     │   (Queues)      │
│                 │     │                 │     │                 │
└─────────────────┘     └─────────────────┘     └────────┬────────┘
                                                          │
                        ┌─────────────────┐               │
                        │                 │               │
                        │ Celery Workers  │◀──────────────┘
                        │ (Task Execution)│
                        │                 │
                        └────────┬────────┘
                                 │
                        ┌────────▼────────┐     ┌─────────────────┐
                        │                 │     │                 │
                        │ OpenRouter API  │     │ Circuit Breaker │
                        │ (Summarization) │◀────│   (Protection)  │
                        │                 │     │                 │
                        └─────────────────┘     └─────────────────┘
```

### Key Features

- **Dual-Queue System**: Separates new tasks from retries to prevent retry storms
- **Circuit Breaker**: Per-worker protection using pybreaker library
- **Dead Letter Queue**: Manages permanently failed tasks
- **OpenRouter-Optimized Error Handling**: Smart classification of API errors with appropriate retry strategies
- **Exponential Backoff**: Smart retry strategy with jitter and error-specific schedules
- **Real-time Monitoring**: Comprehensive health checks and per-worker circuit breaker status
- **Horizontal Scaling**: Dynamic worker scaling with environment variables

## 📁 Project Structure

```
├── src/
│   ├── api/              # FastAPI application
│   │   ├── routers/      # API route handlers
│   │   ├── services/     # Business logic services
│   │   └── schemas.py    # Pydantic models
│   └── worker/           # Celery worker application
│       ├── tasks.py      # Task implementations
│       └── circuit_breaker.py
├── frontend/             # React TypeScript frontend
│   ├── src/
│   └── nginx.conf
├── docs/                 # Documentation
├── tests/                # Test suite
├── utils/                # Utility scripts
└── docker-compose.yml    # Container orchestration
```

## 🛠️ Development

### Prerequisites

- Docker and Docker Compose
- Python 3.11+ (for local development)
- Node.js 18+ and pnpm (for frontend development)

### Environment Setup

1. **Copy environment file:**
   ```bash
   cp .env.example .env
   ```

2. **Configure OpenRouter API:**
   ```bash
   # Edit .env file
   OPENROUTER_API_KEY=your_api_key_here
   ```

3. **Start development environment:**
   ```bash
   docker compose up -d
   ```

### Available Services

| Service | Port | Description |
|---------|------|-------------|
| Frontend | 3000 | React web interface |
| API | 8000 | FastAPI REST API |
| Worker | - | Celery task workers (scalable) |
| Redis | 6379 | Message broker & cache |

### API Endpoints

#### Health & Monitoring
- `GET /health` - Detailed system diagnostics (always returns 200)
- `GET /ready` - Kubernetes readiness check (503 if dependencies down)
- `GET /live` - Kubernetes liveness check (200 if process responding)
- `GET /health/workers` - Per-worker circuit breaker status
- `POST /health/workers/reset-circuit-breaker` - Reset all circuit breakers

#### Business API
- `POST /api/v1/tasks` - Submit new task
- `GET /api/v1/tasks/{task_id}` - Get task status
- `GET /api/v1/queues/status` - Queue statistics

#### Documentation
- `GET /docs` - Interactive API documentation

> **Note**: Health endpoints follow Kubernetes conventions and remain at root level for infrastructure compatibility. `/health` provides detailed diagnostics, `/ready` controls traffic routing, and `/live` determines process restart decisions.

## ⚖️ Scaling Workers

The system supports dynamic worker scaling through environment variables:

### Environment-based Scaling

Configure the number of workers in your `.env` file:

```bash
# Worker scaling configuration
WORKER_REPLICAS=3
CELERY_WORKER_CONCURRENCY=4
```

### Runtime Scaling

Scale workers dynamically without rebuilding:

```bash
# Scale to 5 workers
WORKER_REPLICAS=5 docker compose up -d

# Scale back to 2 workers  
WORKER_REPLICAS=2 docker compose up -d

# Scale to 1 worker for development
WORKER_REPLICAS=1 docker compose up -d
```

### Manual Scaling

Alternatively, use Docker Compose's built-in scaling:

```bash
# Scale to 4 workers
docker compose up -d --scale worker=4

# Scale back to 2 workers
docker compose up -d --scale worker=2
```

### Monitoring Workers

View all worker logs:
```bash
# All workers
docker compose logs worker

# Specific worker
docker compose logs fastapi-async-worker-1
docker compose logs fastapi-async-worker-2
```

## 🧪 Testing

```bash
# Run API tests
cd src/api
uv run pytest

# Run worker tests
cd src/worker
uv run pytest

# Run frontend tests
cd frontend
pnpm test
```

## 📊 Monitoring

### Health Checks

```bash
# Check overall system health
curl http://localhost:8000/health

# Check individual service readiness
curl http://localhost:8000/ready
curl http://localhost:8000/live

# Check per-worker circuit breaker status
curl http://localhost:8000/health/workers
```

### Queue Monitoring

```bash
# View queue statistics
curl http://localhost:8000/api/v1/queues/status

# Inspect dead letter queue
curl http://localhost:8000/api/v1/queues/dlq
```

### Circuit Breaker Management

```bash
# Reset circuit breakers on all workers
curl -X POST http://localhost:8000/health/workers/reset-circuit-breaker

# Monitor worker-specific circuit breaker logs
docker compose logs worker | grep -i "circuit\|breaker"
```

### Debug Utilities

```bash
# Run debug script
python utils/debug.py

# Check worker health individually
docker compose exec fastapi-async-worker-1 celery -A main inspect stats
```

## 🚀 Deployment

### Production Configuration

1. **Update environment variables:**
   ```bash
   DEBUG=false
   LOG_LEVEL=INFO
   OPENROUTER_API_KEY=your_production_key
   WORKER_REPLICAS=6
   CELERY_WORKER_CONCURRENCY=8
   ```

2. **Scale workers for production load:**
   ```bash
   docker compose up -d --scale worker=6
   ```

3. **Enable monitoring:**
   ```bash
   # Add monitoring stack (Prometheus, Grafana)
   docker compose -f docker-compose.yml -f docker-compose.monitoring.yml up -d
   ```

## 🔧 Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `REDIS_URL` | `redis://localhost:6379/0` | Redis connection URL |
| `OPENROUTER_API_KEY` | - | OpenRouter API key |
| `MAX_RETRIES` | `3` | Maximum task retry attempts |
| `WORKER_REPLICAS` | `3` | Number of worker instances |
| `CELERY_WORKER_CONCURRENCY` | `4` | Tasks per worker process |
| `DEBUG` | `false` | Enable debug mode |

### Queue Configuration

- **Primary Queue**: New task submissions
- **Retry Queue**: Failed tasks eligible for retry
- **Scheduled Queue**: Delayed retry tasks
- **Dead Letter Queue**: Permanently failed tasks

### Error Handling & Recovery

The system implements sophisticated error classification with OpenRouter-specific handling:

#### Error Types & Retry Strategies

| Error Type | HTTP Codes | Retry Schedule | Recovery Procedure |
|------------|------------|----------------|-------------------|
| **InsufficientCredits** | 402 | 5min → 10min → 30min | 1. Add credits to OpenRouter account<br>2. Check account balance<br>3. Tasks auto-retry |
| **RateLimitError** | 429 | 1min → 2min → 5min → 10min | 1. Wait for rate limit reset<br>2. Consider upgrading plan<br>3. Scale down request rate |
| **ModelWarmup** | - | 30s → 1min → 2min → 5min | 1. Wait for model initialization<br>2. Use pre-warmed models<br>3. Switch to active models |
| **ServiceUnavailable** | 503 | 5s → 10s → 30s → 1min → 2min | 1. Check OpenRouter status<br>2. Provider fallback automatic<br>3. Wait for service recovery |
| **NetworkTimeout** | 500, 502, 504 | 2s → 5s → 10s → 30s → 1min | 1. Check network connectivity<br>2. Verify DNS resolution<br>3. Check firewall rules |
| **ProviderError** | - | 10s → 30s → 1min → 3min | 1. OpenRouter handles provider fallback<br>2. Try different model if persistent<br>3. Check provider status |
| **ContentFilter** | - | No retry | 1. **Manual Review Required**<br>2. Modify content to comply<br>3. Check OpenRouter content policy |
| **PermanentError** | 400, 401, 403, 404 | No retry | 1. Fix API key/authentication<br>2. Check request parameters<br>3. Verify model availability |

#### Circuit Breaker Recovery

```bash
# Check circuit breaker status
curl http://localhost:8000/health/workers

# Manual circuit breaker reset (if needed)
curl -X POST http://localhost:8000/health/workers/reset-circuit-breaker

# Monitor specific worker
docker compose logs fastapi-async-worker-1 | grep "circuit"
```

#### Dead Letter Queue Recovery

```bash
# View failed tasks
curl http://localhost:8000/api/v1/queues/dlq

# Manual task retry (via API)
curl -X POST http://localhost:8000/api/v1/tasks/{task_id}/retry \
  -H "Content-Type: application/json" \
  -d '{"reset_retry_count": true}'
```

#### Emergency Procedures

1. **High Error Rate**: 
   ```bash
   # Scale down workers temporarily
   WORKER_REPLICAS=1 docker compose up -d
   
   # Reset all circuit breakers
   curl -X POST http://localhost:8000/health/workers/reset-circuit-breaker
   ```

2. **OpenRouter API Issues**:
   ```bash
   # Check system status
   curl http://localhost:8000/health
   
   # Monitor queue buildup
   curl http://localhost:8000/api/v1/queues/status
   
   # Pause task submission if needed
   docker compose stop worker
   ```

3. **Credit Exhaustion**:
   - Add credits to OpenRouter account
   - Tasks will auto-retry when credits available
   - Monitor: `curl http://localhost:8000/health/workers`

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🆘 Support

- **Documentation**: See `docs/` directory
- **Issues**: GitHub Issues
- **Discussions**: GitHub Discussions

## 🔗 Related Projects

- [FastAPI](https://fastapi.tiangolo.com/)
- [Celery](https://docs.celeryproject.org/)
- [Redis](https://redis.io/)
- [OpenRouter](https://openrouter.ai/)