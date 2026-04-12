# FR24 Integration Deployment Guide

**Document Version:** 1.0  
**Date:** 2026-04-11  
**Author:** Dr. Sarah Kim, Technical Product Strategist & Engineering Lead

---

## Pre-Deployment Checklist

- [ ] FR24 API token obtained from https://www.flightradar24.com/developers/api
- [ ] `FR24_API_TOKEN` set in environment
- [ ] Database migration applied (`alembic upgrade head`)
- [ ] `fr24sdk` package installed (`pip install fr24sdk`)
- [ ] Rate limits configured for your FR24 tier
- [ ] All tests passing (including 32 FR24 integration tests)

---

## Deployment Steps

### 1. Install Dependencies

```bash
cd C:\Users\antmi\ground-station\backend

# Install from requirements (includes fr24sdk)
pip install -r requirements.txt

# Or install directly
pip install fr24sdk>=1.0.0
```

### 2. Apply Database Migration

```bash
cd C:\Users\antmi\ground-station\backend

# Check current migration state
alembic current

# Apply all pending migrations (including FR24 fields)
alembic upgrade head

# Verify FR24 migration applied
alembic current  # Should show fr24_001
```

### 3. Configure Environment

**Windows (PowerShell):**
```powershell
$env:FR24_API_TOKEN="your-token-here"
$env:FR24_RATE_LIMIT=60
$env:FR24_ENRICHMENT_LIMIT=50
```

**Linux/macOS:**
```bash
export FR24_API_TOKEN="your-token-here"
export FR24_RATE_LIMIT=60
export FR24_ENRICHMENT_LIMIT=50
export FR24_CACHE_TTL=300
```

**.env file (persistent):**
```bash
# FR24 Configuration
FR24_API_TOKEN=your-fr24-api-token-here
FR24_RATE_LIMIT=60                      # Requests per minute (default: 60)
FR24_ENRICHMENT_LIMIT=50                # Max flights to enrich per batch
FR24_CACHE_TTL=300                      # Cache TTL in seconds
FR24_TIMEOUT=30                         # Request timeout in seconds
FR24_MAX_RETRIES=3                      # Max retry attempts
```

### 4. Validate Configuration

```python
from chemtrail.services import FR24FlightService

# Initialize service
service = FR24FlightService()

# Run health check
health = service.health_check()
print(f"FR24 Status: {health['status']}")
print(f"API Accessible: {health['api_accessible']}")
print(f"Token Valid: {health['token_valid']}")

# Test enrichment
enriched = service.enrich_flight_cache_entry("4b1a02")
if enriched.get('fr24_id'):
    print(f"FR24 enrichment working: {enriched['fr24_id']}")
else:
    print("FR24 enrichment returned no data (may be normal for this flight)")
```

### 5. Start Application

```bash
cd C:\Users\antmi\ground-station\backend

# Development mode
python -m uvicorn main:app --reload

# Production mode
python -m uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4
```

---

## Verification Steps

### 1. Verify Imports

```python
# Test all FR24 imports work
from chemtrail.api import FR24Client, FR24FlightPosition, FR24FlightSummary, FR24FlightTrack
from chemtrail.services import FR24FlightService, FR24Config

print("All FR24 imports successful!")
```

### 2. Verify Database Schema

```python
from sqlalchemy import create_engine, inspect

engine = create_engine("sqlite:///backend/detections.db")
inspector = inspect(engine)

columns = [col['name'] for col in inspector.get_columns('flight_cache')]

fr24_columns = [
    'fr24_id', 'squawk', 'vertical_rate', 'painted_as', 'operating_as',
    'eta', 'origin_icao', 'origin_iata', 'destination_icao', 'destination_iata',
    'flight_track', 'fr24_raw_message', 'data_sources'
]

missing = [col for col in fr24_columns if col not in columns]
if missing:
    print(f"MISSING COLUMNS: {missing}")
else:
    print("All FR24 columns present in flight_cache table!")
```

### 3. Verify Dual-Source Flight Service

```python
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from chemtrail.services import FlightService

engine = create_async_engine("sqlite+aiosqlite:///backend/detections.db")

async def test_dual_source():
    async with AsyncSession(engine) as session:
        flight_service = FlightService(session, fr24_api_token="test-token")
        
        # Verify FR24 service is initialized
        assert flight_service.fr24_service is not None
        print(f"FR24 service initialized: {flight_service.fr24_service is not None}")
        
        # Verify config loaded
        print(f"Rate limit: {flight_service.fr24_service.rate_limit}")
        print(f"Enrichment limit: {flight_service.fr24_service.enrichment_limit}")

import asyncio
asyncio.run(test_dual_source())
```

### 4. Run Test Suite

```bash
cd C:\Users\antmi\ground-station\backend

# Run FR24-specific tests
python -c "import sys; sys.path.insert(0, '.'); import pytest; pytest.main(['tests/chemtrail/test_fr24_integration.py', '-v'])"

# Run all chemtrail tests (verify no regressions)
python -c "import sys; sys.path.insert(0, '.'); import pytest; pytest.main(['tests/chemtrail/', '-v', '--no-cov'])"
```

---

## Rollback Procedure

If FR24 integration causes issues:

### 1. Disable FR24 Enrichment

**Quick disable (no code changes):**
```bash
# Simply unset the token - service will gracefully degrade
unset FR24_API_TOKEN  # Linux/macOS
$env:FR24_API_TOKEN = ""  # PowerShell
```

The `FlightService` will continue operating in OpenSky-only mode.

### 2. Restart Application

```bash
# Stop current process
# Ctrl+C or kill process

# Restart without FR24 token
python -m uvicorn main:app --reload
```

### 3. Optional: Revert Database Changes

```bash
cd C:\Users\antmi\ground-station\backend

# Downgrade by one migration (removes FR24 fields)
alembic downgrade -1

# Or downgrade to specific version
alembic downgrade 5a1c9e7b2d44

# Verify rollback
alembic current
```

### 4. Full Rollback (remove FR24 code)

If complete removal is needed:

1. Remove `fr24sdk` from `requirements.txt`
2. Remove `fr24sdk` from `pyproject.toml`
3. Uninstall package: `pip uninstall fr24sdk`
4. Revert code changes in:
   - `backend/chemtrail/api/fr24_client.py`
   - `backend/chemtrail/services/fr24_flight_service.py`
   - `backend/chemtrail/services/flight_service.py`
   - `backend/chemtrail/archive/detection_service.py`
   - `backend/chemtrail/api/__init__.py`
   - `backend/chemtrail/services/__init__.py`
   - `backend/chemtrail/__init__.py`
5. Remove FR24 fields from `backend/db/models.py`
6. Delete migration file: `backend/alembic/versions/fr24_001_add_fr24_fields_to_flight_cache.py`

---

## Monitoring

### Application Logs

```bash
# Check FR24-related logs
grep "FR24" application.log

# Check for errors
grep -i "fr24.*error" application.log

# Check enrichment activity
grep "enriched.*flights" application.log
```

### Health Check Endpoint (when implemented)

```bash
curl http://localhost:8000/api/health/fr24
```

Expected response:
```json
{
    "status": "healthy",
    "api_accessible": true,
    "token_valid": true,
    "last_check": "2026-04-11T12:00:00Z"
}
```

### Manual Health Check

```python
from chemtrail.services import FR24FlightService

service = FR24FlightService()
health = service.health_check()

print(f"Status: {health['status']}")
print(f"Token Valid: {health['token_valid']}")
print(f"Last Check: {health['last_check']}")
```

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| **Token validation failed** | Verify `FR24_API_TOKEN` is correct and not expired. Check FR24 dashboard for API status. |
| **Rate limit exceeded** | Reduce `FR24_RATE_LIMIT` or upgrade your FR24 API tier. Check FR24 dashboard for quota. |
| **Connection timeout** | Check network connectivity. Increase `FR24_TIMEOUT` environment variable. |
| **No FR24 data in archive** | Verify enrichment is called in `DetectionService`. Check logs for "FR24 enrichment failed" messages. |
| **ImportError: No module named fr24sdk** | Run `pip install fr24sdk` or `pip install -r requirements.txt` |
| **Database column missing** | Run `alembic upgrade head` to apply migration |
| **Health check returns "degraded"** | Token may be invalid or rate-limited. Check FR24 API dashboard |
| **Partial enrichment** | Some flights may not have FR24 data. This is normal - fallback to OpenSky data |

### Debug Mode

Enable verbose logging for FR24 operations:

```python
import logging
logging.getLogger('chemtrail.services.fr24_flight_service').setLevel(logging.DEBUG)
```

---

## Performance Tuning

### Rate Limit Configuration

FR24 API tiers have different rate limits:

| Tier | Requests/Minute | Recommended Setting |
|------|-----------------|---------------------|
| Free | 60 | `FR24_RATE_LIMIT=50` (leave headroom) |
| Silver | 120 | `FR24_RATE_LIMIT=100` |
| Gold | 300 | `FR24_RATE_LIMIT=250` |
| Enterprise | Custom | Configure per contract |

### Enrichment Batch Size

Control how many flights are enriched per batch:

```bash
FR24_ENRICHMENT_LIMIT=50  # Default, good for most deployments
FR24_ENRICHMENT_LIMIT=100  # For high-traffic deployments
FR24_ENRICHMENT_LIMIT=20   # For rate-limited environments
```

### Cache TTL

Control how long enriched data is cached:

```bash
FR24_CACHE_TTL=300   # Default (5 minutes)
FR24_CACHE_TTL=600   # Reduce API calls (10 minutes)
FR24_CACHE_TTL=60    # High freshness (1 minute)
```

---

## Environment Variables Reference

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `FR24_API_TOKEN` | Yes (for enrichment) | None | Your FR24 API token |
| `FR24_RATE_LIMIT` | No | 60 | Max requests per minute |
| `FR24_ENRICHMENT_LIMIT` | No | 50 | Max flights to enrich per batch |
| `FR24_CACHE_TTL` | No | 300 | Cache TTL in seconds |
| `FR24_TIMEOUT` | No | 30 | Request timeout in seconds |
| `FR24_MAX_RETRIES` | No | 3 | Max retry attempts on failure |

---

## Support

For FR24 API-specific issues:
- Documentation: https://www.flightradar24.com/developers/api
- Support: api@flightradar24.com

For integration issues:
- Check `docs/chemtrail-tracker/FINALIZATION_PLAN.md`
- Run test suite: `pytest tests/chemtrail/test_fr24_integration.py -v`

---

*Document prepared by Dr. Sarah Kim, Technical Product Strategist & Engineering Lead*  
*FR24 Integration Deployment Guide v1.0*
