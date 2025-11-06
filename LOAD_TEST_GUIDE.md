# Load Testing Guide - 10,000 Concurrent Requests

## Overview
This load test will simulate 10,000 concurrent requests to test the performance of the e-commerce application under high load.

## Test Configuration

### Test Scenarios (10,000 total requests):
- **Health Checks** (20%): 2,000 requests to `/health`
- **List Products** (30%): 3,000 requests to `/products`
- **Check Stock Product 1** (25%): 2,500 requests to `/stock?product_id=1`
- **Check Stock Product 2** (15%): 1,500 requests to `/stock?product_id=2`
- **Purchase Orders** (10%): 1,000 POST requests to `/purchase`

### Load Test Settings:
- Total Requests: 10,000
- Concurrent Workers: 100 (async workers)
- Timeout per request: 30 seconds
- Base URL: http://localhost:8000

## How to Run the Load Test

### Prerequisites:
1. Ensure all services are running:
   ```bash
   docker compose ps
   ```
   Should show: app, kafka, redis, zookeeper, prometheus, grafana, node-exporter as "Up"

2. Open Grafana dashboard BEFORE starting test:
   - URL: http://localhost:3000
   - Dashboard: "System and App Metrics"
   - This will show real-time metrics during the test

### Run the Test:

```bash
python load_test.py
```

The script will:
1. Show test configuration
2. Wait for you to press ENTER
3. Execute 10,000 requests with 100 concurrent workers
4. Show progress every 500 requests
5. Display detailed results
6. Save results to JSON file

## What to Monitor

### In Terminal:
- Progress updates (every 500 requests)
- Success/failure rates
- Response times (min, max, mean, p50, p95, p99)
- Errors and timeouts

### In Grafana (http://localhost:3000):
Watch these panels during the test:

1. **CPU Usage (%)** - Should spike during test
2. **Memory Usage** - Watch for memory consumption
3. **HTTP Request Rate** - Should show ~100-200 req/s
4. **Latency p50/p95/p99** - Watch response times increase under load

### In Prometheus (http://localhost:9090):
- Query: `rate(http_requests_total[1m])` - Request rate
- Query: `http_request_duration_seconds_bucket` - Latency histogram

## Expected Results

### Good Performance:
- ✅ Success rate > 95%
- ✅ p50 latency < 100ms
- ✅ p95 latency < 500ms
- ✅ p99 latency < 1000ms
- ✅ Requests/sec > 100
- ✅ No timeouts or minimal timeouts
- ✅ CPU usage < 80%

### Performance Issues:
- ⚠️ Success rate < 90%
- ⚠️ p99 latency > 2000ms
- ⚠️ Many timeouts
- ⚠️ CPU usage > 95%
- ⚠️ Memory keeps increasing (memory leak)

## Test Results

The load test will generate a JSON file with detailed results:
- `load_test_results_YYYYMMDD_HHMMSS.json`

Example output:
```json
{
  "total_time": 45.23,
  "total_requests": 10000,
  "successful": 9850,
  "failed": 150,
  "timeouts": 0,
  "requests_per_second": 221.05,
  "response_times": {
    "min_ms": 5.23,
    "max_ms": 1245.67,
    "mean_ms": 123.45,
    "median_ms": 95.32,
    "p95_ms": 456.78,
    "p99_ms": 789.12
  }
}
```

## Optimizations to Try

If performance is poor, try these optimizations:

### 1. Increase Docker Resources:
- Docker Desktop → Settings → Resources
- Increase CPU cores (4-8)
- Increase Memory (4-8 GB)

### 2. Scale Kafka:
- Add more partitions to the purchases topic
- Increase Kafka broker memory

### 3. Redis Optimization:
- Enable Redis persistence if needed
- Tune Redis maxmemory settings

### 4. Application Tuning:
- Increase Hypercorn worker threads
- Optimize database queries
- Add connection pooling

### 5. Database:
- Switch from SQLite to PostgreSQL for better concurrency
- Add indexes on frequently queried columns

## Stress Testing Variants

### Quick Test (1,000 requests):
Edit `load_test.py`:
```python
tester = LoadTester(
    base_url="http://localhost:8000",
    total_requests=1000,  # Change to 1000
    concurrent_workers=50  # Change to 50
)
```

### Extreme Load (50,000 requests):
```python
tester = LoadTester(
    base_url="http://localhost:8000",
    total_requests=50000,  # Change to 50000
    concurrent_workers=200  # Change to 200
)
```

### Purchase-Heavy Test:
Modify scenarios to make 50% purchases:
```python
scenarios = [
    ("/health", "GET", None, 0.10),
    ("/products", "GET", None, 0.20),
    ("/stock?product_id=1", "GET", None, 0.20),
    ("/purchase", "POST", {"product_id": 1, "quantity": 1}, 0.50),
]
```

## Monitoring During Test

### Watch Docker Logs:
```bash
# In separate terminals:
docker logs -f gsg-app
docker logs -f gsg-kafka
docker logs -f gsg-redis
```

### System Resource Monitoring:
```bash
# Windows Task Manager
# Or Docker Desktop → Containers → gsg-app → Stats
```

## Troubleshooting

### "Connection Refused" errors:
- Check if app is running: `docker ps`
- Verify port 8000 is exposed: `curl http://localhost:8000/health`

### Many Timeouts:
- Services may be overloaded
- Increase timeout in load_test.py
- Reduce concurrent_workers

### Kafka Errors in Logs:
- Normal during high load
- Purchases may queue up
- Check Kafka logs: `docker logs gsg-kafka`

### Memory Issues:
- Check for memory leaks
- Monitor Grafana Memory Usage panel
- Restart containers if needed

## After the Test

1. **Review Results**:
   - Check generated JSON file
   - Look at Grafana dashboard
   - Identify bottlenecks

2. **Check Application State**:
   ```bash
   curl http://localhost:8000/health
   curl http://localhost:8000/products
   ```

3. **Verify Data Consistency**:
   ```bash
   curl http://localhost:8000/debug/stock?product_id=1
   ```
   Check that db_stock and redis_stock match

4. **Reset if Needed**:
   ```bash
   docker compose restart app
   ```

## Performance Benchmarks

### Target SLAs:
- p50 latency: < 50ms
- p95 latency: < 200ms
- p99 latency: < 500ms
- Success rate: > 99%
- Throughput: > 200 req/s

### Typical Results (on 4 CPU, 8GB RAM):
- p50: ~30-80ms
- p95: ~150-400ms
- p99: ~300-800ms
- Success: 95-99%
- Throughput: 150-250 req/s

## Next Steps

After running the load test:
1. Analyze Grafana dashboards for bottlenecks
2. Check Prometheus metrics for anomalies
3. Review application logs for errors
4. Optimize based on findings
5. Re-run test to verify improvements

Happy Load Testing! 🚀

