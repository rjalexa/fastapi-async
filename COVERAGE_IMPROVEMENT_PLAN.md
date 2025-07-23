# Coverage Improvement Plan

## Current Status
- **Current Coverage**: 31%
- **Target Coverage**: 80%
- **Gap**: 49 percentage points

## Priority Areas for Improvement

### 1. Critical Files (High Impact)
These files have the most lines and lowest coverage:

#### `src/api/services.py` (692 lines, 7% coverage)
- **Impact**: +45% coverage potential
- **Priority**: CRITICAL
- **Actions**:
  - Add unit tests for task management functions
  - Add tests for Redis operations
  - Add tests for task state transitions
  - Add tests for error handling

#### `src/worker/consumer.py` (62 lines, 0% coverage)
- **Impact**: +2% coverage potential
- **Priority**: HIGH
- **Actions**:
  - Add tests for Celery consumer setup
  - Add tests for task routing
  - Add tests for worker lifecycle

#### `src/worker/circuit_breaker.py` (150 lines, 11% coverage)
- **Impact**: +4% coverage potential
- **Priority**: HIGH
- **Actions**:
  - Add tests for circuit breaker states
  - Add tests for failure thresholds
  - Add tests for recovery mechanisms

#### `src/worker/openrouter_state_reporter.py` (155 lines, 12% coverage)
- **Impact**: +4% coverage potential
- **Priority**: HIGH
- **Actions**:
  - Add tests for state reporting
  - Add tests for API communication
  - Add tests for error handling

### 2. API Router Tests (Medium Impact)
Multiple router files with low coverage:

#### `src/api/routers/workers.py` (113 lines, 10% coverage)
- Add integration tests for worker endpoints
- Add tests for worker status monitoring

#### `src/api/routers/queues.py` (125 lines, 15% coverage)
- Add tests for queue management
- Add tests for queue statistics

#### `src/api/routers/redis.py` (50 lines, 18% coverage)
- Add tests for Redis monitoring endpoints

### 3. Fix Existing Test Issues

#### API Test Fixtures
- Fix async fixture issues in `tests/conftest.py`
- Fix test client setup problems
- Resolve dependency injection issues

#### Worker Test Mocking
- Fix AsyncMock usage in worker tests
- Resolve coroutine context manager issues
- Fix Redis mocking problems

## Implementation Strategy

### Phase 1: Fix Existing Tests (Week 1)
1. Fix conftest.py fixture issues
2. Fix API test failures
3. Fix worker test mocking issues
4. Ensure all existing tests pass

### Phase 2: Add Critical Coverage (Week 2)
1. Add comprehensive tests for `src/api/services.py`
2. Add tests for `src/worker/consumer.py`
3. Add tests for circuit breaker functionality

### Phase 3: Add Router Coverage (Week 3)
1. Add API router tests
2. Add integration tests
3. Add error handling tests

### Phase 4: Optimization (Week 4)
1. Add edge case tests
2. Add performance tests
3. Optimize test execution time
4. Achieve 80%+ coverage

## Expected Coverage Gains

| Component | Current | Target | Gain |
|-----------|---------|--------|------|
| services.py | 7% | 80% | +35% |
| consumer.py | 0% | 90% | +2% |
| circuit_breaker.py | 11% | 80% | +4% |
| openrouter_state_reporter.py | 12% | 80% | +4% |
| API routers | 15-35% | 70% | +8% |
| **Total** | **31%** | **82%** | **+51%** |

## Test Categories to Add

### Unit Tests
- Individual function testing
- Error condition testing
- Edge case handling
- Input validation

### Integration Tests
- API endpoint testing
- Database operations
- External service mocking
- End-to-end workflows

### Performance Tests
- Load testing for critical paths
- Memory usage validation
- Timeout handling

### Error Handling Tests
- Exception propagation
- Retry mechanisms
- Circuit breaker behavior
- Graceful degradation
