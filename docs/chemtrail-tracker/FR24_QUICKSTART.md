# FR24 Integration Quickstart Guide

**Version:** 1.0  
**Date:** 2026-04-11  
**Status:** Production Ready

Quick start guide for integrating Flightradar24 (FR24) flight data into the Chemtrail Webcam Tracker system.

---

## Overview

The FR24 integration adds dual-source flight data to the Chemtrail system:

- **Primary Source:** OpenSky Network (real-time positions)
- **Enrichment Source:** Flightradar24 (rich metadata, historical data, flight tracks)

**Benefits:**
- Airline branding (`painted_as`, `operating_as`)
- Detailed airport codes (ICAO/IATA)
- Flight track history (positional points)
- Historical data access (since 2016-05-11)
- Enhanced correlation scoring

---

## Prerequisites

- Python 3.9+
- Existing Chemtrail Webcam Tracker installation
- FR24 API token (see Setup below)

---

## Step 1: Get FR24 API Token

1. Visit https://www.flightradar24.com/developers/api
2. Sign up for an API account
3. Choose your tier (Free: 60 req/min, 7-day history)
4. Copy your API token

---

## Step 2: Install Dependencies

```bash
cd C:\Users\antmi\ground-station\backend

# Install from requirements (includes fr24sdk)
pip install -r requirements.txt

# Or install directly
pip install fr24sdk>=1.0.0
```

**Verify installation:**
```bash
python -c "import fr24sdk; print(f'fr24sdk version: {fr24sdk.__version__}')"
```

---

## Step 3: Configure Environment

**Windows (PowerShell):**
```powershell
$env:FR24_API_TOKEN="your-fr24-api-token-here"
$env:FR24_RATE_LIMIT=60
$env:FR24_ENRICHMENT_LIMIT=50
```

**Linux/macOS:**
```bash
export FR24_API_TOKEN="your-fr24-api-token-here"
export FR24_RATE_LIMIT=60
export FR24_ENRICHMENT_LIMIT=50
```

**.env file (persistent):**
```bash
# FR24 Configuration
FR24_API_TOKEN=your-fr24-api-token-here
FR24_RATE_LIMIT=60                      # Requests per minute
FR24_ENRICHMENT_LIMIT=50                # Max flights to enrich per batch
FR24_CACHE_TTL=300                      # Cache TTL in seconds
FR24_TIMEOUT=30                         # Request timeout in seconds
FR24_MAX_RETRIES=3                      # Max retry attempts
```

---

## Step 4: Apply Database Migration

```bash
cd C:\Users\antmi\ground-station\backend

# Check current migration state
alembic current

# Apply all pending migrations (including FR24 fields)
alembic upgrade head

# Verify FR24 migration applied
alembic current  # Should show fr24_001
```

**Verify FR24 fields in database:**
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

---

## Step 5: Test FR24 Connectivity

**Basic health check:**
```python
from chemtrail.services import FR24FlightService

# Initialize service (reads FR24_API_TOKEN from env)
service = FR24FlightService()

# Run health check
health = service.health_check()
print(f"Status: {health['status']}")
print(f"API Accessible: {health['api_accessible']}")
print(f"Token Valid: {health['token_valid']}")
```

**Expected output:**
```
Status: healthy
API Accessible: True
Token Valid: True
```

**Test enrichment:**
```python
from chemtrail.services import FR24FlightService

service = FR24FlightService()

# Enrich a flight (example ICAO hex)
enriched = service.enrich_flight_cache_entry("4b1a02")

if enriched.get('fr24_id'):
    print(f"FR24 enrichment successful!")
    print(f"  FR24 ID: {enriched['fr24_id']}")
    print(f"  Painted As: {enriched.get('painted_as')}")
    print(f"  Flight Track Points: {len(enriched.get('flight_track', []))}")
else:
    print("No FR24 data found for this flight (may be normal)")
```

---

## Step 6: Run Test Suite

```bash
cd C:\Users\antmi\ground-station\backend

# Run FR24-specific tests
pytest tests/chemtrail/test_fr24_integration.py -v

# Expected: 32 tests passing
```

**Expected output:**
```
tests/chemtrail/test_fr24_integration.py::TestFR24ClientInitialization - PASSED
tests/chemtrail/test_fr24_integration.py::TestFR24ClientMapping - PASSED
tests/chemtrail/test_fr24_integration.py::TestFR24ClientMethods - PASSED
tests/chemtrail/test_fr24_integration.py::TestFR24FlightService - PASSED
tests/chemtrail/test_fr24_integration.py::TestDualSourceFlightService - PASSED
tests/chemtrail/test_fr24_integration.py::TestCorrelationScore - PASSED

==================== 32 passed in X.XXs ====================
```

**Run full test suite (verify no regressions):**
```bash
pytest tests/chemtrail/ -v --no-cov
# Expected: 318 tests passing (286 original + 32 FR24)
```

---

## Usage Examples

### Basic FR24 Service Usage

```python
from chemtrail.services import FR24FlightService

# Initialize with environment variables
service = FR24FlightService()

# Health check
health = service.health_check()
print(f"Status: {health['status']}")  # healthy | degraded | unhealthy

# Enrich flight data
enriched = service.enrich_flight_cache_entry("4b1a02")
print(enriched)  # Contains fr24_id, painted_as, flight_track, etc.
```

### Configuration with FR24Config

```python
from chemtrail.services import FR24Config, FR24FlightService

# Load from environment
config = FR24Config.from_env()

# Or specify directly
config = FR24Config(
    api_token="your-token",
    rate_limit=60,
    enrichment_limit=50,
)

service = FR24FlightService(config=config)
```

### Dual-Source Flight Service

```python
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from chemtrail.services import FlightService

engine = create_async_engine("sqlite+aiosqlite:///backend/detections.db")

async with AsyncSession(engine) as session:
    # FlightService automatically uses both OpenSky and FR24
    flight_service = FlightService(session, fr24_api_token="your-token")
    
    # Get flights near position (includes FR24 data)
    flights = await flight_service.get_flights_near_position(
        lat=47.6062,
        lon=-122.3321,
        radius_km=50,
    )
    
    # Check data sources for each flight
    for flight in flights:
        sources = flight.get("data_sources", [])
        print(f"Flight {flight['icao24']}: sources={sources}")
        # Output: Flight 4b1a02: sources=['opensky', 'fr24']
```

### Detection Pipeline with FR24 Enrichment

```python
from chemtrail.archive.detection_service import DetectionService
from chemtrail.services import FlightService, FR24FlightService

# Initialize services
flight_service = FlightService(session, fr24_api_token="token")
fr24_service = FR24FlightService(api_token="token")

# Create detection service with FR24 enrichment
detection_service = DetectionService(
    session=session,
    vector_store=vector_store,
    flight_service=flight_service,
    contrail_detector=detector,
    fr24_service=fr24_service,
)

# Process detections with automatic FR24 enrichment
results = await detection_service.process_detection_batch(
    chunks=chunks,
    camera_id=camera_id,
    camera_metadata=metadata,
    apply_overlay=True,
)
```

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| **Token validation failed** | Verify `FR24_API_TOKEN` is correct. Check FR24 dashboard for API status. |
| **Rate limit exceeded** | Reduce `FR24_RATE_LIMIT` or upgrade your FR24 API tier. |
| **Connection timeout** | Check network connectivity. Increase `FR24_TIMEOUT`. |
| **No FR24 data in archive** | Verify enrichment is called in `DetectionService`. Check logs for errors. |
| **ImportError: No module named fr24sdk** | Run `pip install fr24sdk` or `pip install -r requirements.txt` |
| **Database column missing** | Run `alembic upgrade head` to apply migration |
| **Health check returns "degraded"** | Token may be invalid or rate-limited. Check FR24 API dashboard |
| **Partial enrichment** | Some flights may not have FR24 data. This is normal - system continues in OpenSky-only mode |

**Enable debug logging:**
```python
import logging
logging.getLogger('chemtrail.services.fr24_flight_service').setLevel(logging.DEBUG)
```

---

## Verification Commands

### Verify All Imports

```python
# All FR24 imports
from chemtrail.api import FR24Client, FR24FlightPosition, FR24FlightSummary, FR24FlightTrack
from chemtrail.services import FR24FlightService, FlightService
from chemtrail import FR24FlightService  # Top-level

print("All FR24 imports successful!")

# Verify service initialization
service = FR24FlightService()
print(f"Service initialized: {service is not None}")

# Verify config loading
from chemtrail.services import FR24Config
config = FR24Config.from_env()
print(f"Config loaded: api_token={'SET' if config.api_token else 'NOT SET'}")
```

### Verify Database Schema

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
    print("All FR24 columns present!")
```

### Verify Service Health

```python
from chemtrail.services import FR24FlightService

service = FR24FlightService()
health = service.health_check()

print(f"Status: {health['status']}")
print(f"API Accessible: {health['api_accessible']}")
print(f"Token Valid: {health['token_valid']}")
print(f"Last Check: {health['last_check']}")
```

---

## Rollback Procedure

If you need to disable FR24:

**Quick disable (no code changes):**
```bash
# Simply unset the token - service will gracefully degrade
unset FR24_API_TOKEN  # Linux/macOS
$env:FR24_API_TOKEN = ""  # PowerShell
```

The `FlightService` will continue operating in OpenSky-only mode.

**Optional: Revert database changes:**
```bash
cd C:\Users\antmi\ground-station\backend

# Downgrade by one migration (removes FR24 fields)
alembic downgrade -1

# Verify rollback
alembic current
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

## Next Steps

After completing this quickstart:

1. **Review full documentation:**
   - `FR24_INTEGRATION_ARCHITECTURE.md` - Detailed architecture
   - `FR24_DEPLOYMENT.md` - Production deployment guide
   - `FR24_IMPLEMENTATION_STATUS.md` - Implementation status report

2. **Monitor FR24 usage:**
   - Check FR24 dashboard for API quota
   - Review application logs for enrichment activity

3. **Tune configuration:**
   - Adjust `FR24_RATE_LIMIT` for your tier
   - Configure `FR24_ENRICHMENT_LIMIT` for your workload

---

**FR24 API Support:**
- Documentation: https://www.flightradar24.com/developers/api
- Email: api@flightradar24.com

**Integration Status:** Production Ready  
**Tests Passing:** 32/32 FR24 tests, 318 total tests  
**Last Updated:** 2026-04-11
