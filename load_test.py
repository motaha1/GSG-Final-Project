"""
Load Testing Script for E-Commerce Application
Tests performance under high concurrent load (10,000 requests)
Monitors Docker container CPU, RAM from Prometheus, and calculates p50/p90/p95 latency
"""
import asyncio
import aiohttp
import time
from datetime import datetime
from collections import defaultdict
import json
import statistics
import requests


class LoadTester:
    def __init__(self, base_url="http://localhost:8000", total_requests=10000, concurrent_workers=100, prometheus_url="http://localhost:9090"):
        self.base_url = base_url
        self.prometheus_url = prometheus_url
        self.total_requests = total_requests
        self.concurrent_workers = concurrent_workers
        self.results = {
            "successful": 0,
            "failed": 0,
            "timeouts": 0,
            "response_times": [],
            "errors": defaultdict(int),
            "status_codes": defaultdict(int),
        }
        # Prometheus metrics storage
        self.test_start_time = None
        self.test_end_time = None

    async def make_request(self, session, endpoint, method="GET", json_data=None):
        """Make a single HTTP request and track metrics"""
        url = f"{self.base_url}{endpoint}"
        start_time = time.time()

        try:
            if method == "GET":
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as response:
                    await response.text()
                    elapsed = time.time() - start_time
                    self.results["response_times"].append(elapsed)
                    self.results["status_codes"][response.status] += 1
                    if response.status == 200:
                        self.results["successful"] += 1
                    else:
                        self.results["failed"] += 1
                    return elapsed, response.status
            elif method == "POST":
                async with session.post(url, json=json_data, timeout=aiohttp.ClientTimeout(total=30)) as response:
                    await response.text()
                    elapsed = time.time() - start_time
                    self.results["response_times"].append(elapsed)
                    self.results["status_codes"][response.status] += 1
                    if response.status == 200:
                        self.results["successful"] += 1
                    else:
                        self.results["failed"] += 1
                    return elapsed, response.status
        except asyncio.TimeoutError:
            elapsed = time.time() - start_time
            self.results["timeouts"] += 1
            self.results["errors"]["Timeout"] += 1
            return elapsed, "TIMEOUT"
        except Exception as e:
            elapsed = time.time() - start_time
            self.results["failed"] += 1
            self.results["errors"][str(type(e).__name__)] += 1
            return elapsed, "ERROR"

    def query_prometheus(self, query, start_time=None, end_time=None):
        """Query Prometheus for metrics during test period"""
        try:
            if start_time and end_time:
                # Query range
                params = {
                    'query': query,
                    'start': start_time,
                    'end': end_time,
                    'step': '15s'
                }
                response = requests.get(f"{self.prometheus_url}/api/v1/query_range", params=params, timeout=10)
            else:
                # Instant query
                response = requests.get(f"{self.prometheus_url}/api/v1/query", params={'query': query}, timeout=10)

            if response.status_code == 200:
                data = response.json()
                if data['status'] == 'success':
                    return data['data']['result']
            return None
        except Exception as e:
            print(f"Warning: Failed to query Prometheus: {e}")
            return None

    def get_container_metrics(self):
        """Get application CPU and RAM metrics from Prometheus (per Python process)"""
        if not self.test_start_time or not self.test_end_time:
            return None

        metrics = {}

        # Query CPU usage for application processes (not whole device)
        cpu_query = 'rate(process_cpu_seconds_total{job="app"}[1m]) * 100'
        cpu_results = self.query_prometheus(cpu_query, self.test_start_time, self.test_end_time)

        if cpu_results:
            all_cpu_values = []
            for result in cpu_results:
                instance = result['metric'].get('instance', 'unknown')
                values = [float(v[1]) for v in result['values']]
                all_cpu_values.extend(values)
                metrics[f'cpu_{instance}'] = {
                    'min': min(values),
                    'max': max(values),
                    'avg': statistics.mean(values)
                }

            if all_cpu_values:
                metrics['cpu_total'] = {
                    'min': min(all_cpu_values),
                    'max': max(all_cpu_values),
                    'avg': statistics.mean(all_cpu_values),
                    'median': statistics.median(all_cpu_values)
                }

        # Query RAM usage for application processes (not whole device)
        ram_query = 'process_resident_memory_bytes{job="app"} / 1024 / 1024'
        ram_results = self.query_prometheus(ram_query, self.test_start_time, self.test_end_time)

        if ram_results:
            all_ram_values = []
            for result in ram_results:
                instance = result['metric'].get('instance', 'unknown')
                values = [float(v[1]) for v in result['values']]
                all_ram_values.extend(values)
                metrics[f'ram_{instance}'] = {
                    'min': min(values),
                    'max': max(values),
                    'avg': statistics.mean(values)
                }

            if all_ram_values:
                metrics['ram_total'] = {
                    'min': min(all_ram_values),
                    'max': max(all_ram_values),
                    'avg': statistics.mean(all_ram_values),
                    'median': statistics.median(all_ram_values)
                }

        return metrics

    async def worker(self, session, task_queue, progress_callback=None):
        """Worker that processes tasks from the queue"""
        while True:
            try:
                task = await asyncio.wait_for(task_queue.get(), timeout=0.1)
                if task is None:  # Poison pill
                    break

                endpoint, method, data = task
                await self.make_request(session, endpoint, method, data)

                if progress_callback:
                    progress_callback()

                task_queue.task_done()
            except asyncio.TimeoutError:
                continue

    async def run_test(self, scenarios):
        """
        Run load test with specified scenarios
        scenarios: list of tuples (endpoint, method, json_data, weight)
        weight: proportion of requests (e.g., 0.5 = 50% of requests)
        """
        print(f"\n{'='*80}")
        print(f"LOAD TEST STARTED")
        print(f"{'='*80}")
        print(f"Base URL: {self.base_url}")
        print(f"Prometheus URL: {self.prometheus_url}")
        print(f"Total Requests: {self.total_requests:,}")
        print(f"Concurrent Workers: {self.concurrent_workers}")
        print(f"Test Scenarios: {len(scenarios)}")
        print(f"{'='*80}\n")

        # Record start time for Prometheus query
        self.test_start_time = time.time()

        # Create task queue
        task_queue = asyncio.Queue()

        # Distribute requests across scenarios based on weights
        for endpoint, method, data, weight in scenarios:
            count = int(self.total_requests * weight)
            for _ in range(count):
                await task_queue.put((endpoint, method, data))

        # Progress tracking
        completed = [0]
        def progress_callback():
            completed[0] += 1
            if completed[0] % 500 == 0 or completed[0] == self.total_requests:
                percentage = (completed[0] / self.total_requests) * 100
                print(f"Progress: {completed[0]:,}/{self.total_requests:,} ({percentage:.1f}%)")

        # Create workers
        start_time = time.time()

        connector = aiohttp.TCPConnector(limit=self.concurrent_workers, limit_per_host=self.concurrent_workers)
        async with aiohttp.ClientSession(connector=connector) as session:
            workers = [
                asyncio.create_task(self.worker(session, task_queue, progress_callback))
                for _ in range(self.concurrent_workers)
            ]

            # Wait for all tasks to complete
            await task_queue.join()

            # Stop workers
            for _ in range(self.concurrent_workers):
                await task_queue.put(None)

            await asyncio.gather(*workers)

        total_time = time.time() - start_time

        # Record end time for Prometheus query
        self.test_end_time = time.time()

        # Fetch application metrics from Prometheus
        print("\nFetching application metrics from Prometheus...")
        container_metrics = self.get_container_metrics()

        # Calculate statistics
        self.print_results(total_time, container_metrics)

    def print_results(self, total_time, container_metrics=None):
        """Print detailed test results"""
        print(f"\n{'='*80}")
        print(f"LOAD TEST RESULTS")
        print(f"{'='*80}\n")

        # Summary
        print("SUMMARY:")
        print(f"  Total Time: {total_time:.2f} seconds")
        print(f"  Total Requests: {self.total_requests:,}")
        print(f"  Successful: {self.results['successful']:,} ({self.results['successful']/self.total_requests*100:.1f}%)")
        print(f"  Failed: {self.results['failed']:,} ({self.results['failed']/self.total_requests*100:.1f}%)")
        print(f"  Timeouts: {self.results['timeouts']:,} ({self.results['timeouts']/self.total_requests*100:.1f}%)")
        print(f"  Requests/sec: {self.total_requests/total_time:.2f}")

        # Response times with p50, p90, p95
        if self.results["response_times"]:
            response_times = sorted(self.results["response_times"])
            p50_index = int(len(response_times) * 0.50)
            p90_index = int(len(response_times) * 0.90)
            p95_index = int(len(response_times) * 0.95)
            p99_index = int(len(response_times) * 0.99)

            print(f"\nRESPONSE TIMES (LATENCY):")
            print(f"  Min: {min(response_times)*1000:.2f} ms")
            print(f"  Max: {max(response_times)*1000:.2f} ms")
            print(f"  Mean: {statistics.mean(response_times)*1000:.2f} ms")
            print(f"  p50 (Median): {response_times[p50_index]*1000:.2f} ms")
            print(f"  p90: {response_times[p90_index]*1000:.2f} ms")
            print(f"  p95: {response_times[p95_index]*1000:.2f} ms")
            print(f"  p99: {response_times[p99_index]*1000:.2f} ms")

        # Application metrics from Prometheus
        if container_metrics:
            print(f"\n{'='*80}")
            print(f"APPLICATION METRICS (from Prometheus)")
            print(f"Note: These are per-application instance, NOT whole device")
            print(f"{'='*80}")

            # Total CPU
            if 'cpu_total' in container_metrics:
                cpu = container_metrics['cpu_total']
                print(f"\nAPPLICATION CPU USAGE (Total):")
                print(f"  Min: {cpu['min']:.2f}%")
                print(f"  Max: {cpu['max']:.2f}%")
                print(f"  Average: {cpu['avg']:.2f}%")
                print(f"  Median: {cpu['median']:.2f}%")

            # Per-instance CPU
            for key, value in container_metrics.items():
                if key.startswith('cpu_app'):
                    instance_name = key.replace('cpu_', '')
                    print(f"\n  {instance_name}:")
                    print(f"    Min: {value['min']:.2f}%")
                    print(f"    Max: {value['max']:.2f}%")
                    print(f"    Avg: {value['avg']:.2f}%")

            # Total RAM
            if 'ram_total' in container_metrics:
                ram = container_metrics['ram_total']
                print(f"\nAPPLICATION RAM USAGE (Total):")
                print(f"  Min: {ram['min']:.2f} MB")
                print(f"  Max: {ram['max']:.2f} MB")
                print(f"  Average: {ram['avg']:.2f} MB")
                print(f"  Median: {ram['median']:.2f} MB")

            # Per-instance RAM
            for key, value in container_metrics.items():
                if key.startswith('ram_app'):
                    instance_name = key.replace('ram_', '')
                    print(f"\n  {instance_name}:")
                    print(f"    Min: {value['min']:.2f} MB")
                    print(f"    Max: {value['max']:.2f} MB")
                    print(f"    Avg: {value['avg']:.2f} MB")
        else:
            print(f"\nNote: Could not fetch application metrics from Prometheus")
            print(f"      Make sure Prometheus is running at {self.prometheus_url}")
            print(f"      And your application is exporting metrics")

        # Status codes
        if self.results["status_codes"]:
            print(f"\nSTATUS CODES:")
            for code, count in sorted(self.results["status_codes"].items()):
                print(f"  {code}: {count:,} ({count/self.total_requests*100:.1f}%)")

        # Errors
        if self.results["errors"]:
            print(f"\nERRORS:")
            for error, count in sorted(self.results["errors"].items(), key=lambda x: x[1], reverse=True):
                print(f"  {error}: {count:,}")

        print(f"\n{'='*80}")

        # Save results to JSON
        results_file = f"load_test_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

        response_times = sorted(self.results["response_times"]) if self.results["response_times"] else []

        results_data = {
            "total_time": total_time,
            "total_requests": self.total_requests,
            "successful": self.results["successful"],
            "failed": self.results["failed"],
            "timeouts": self.results["timeouts"],
            "requests_per_second": self.total_requests/total_time,
            "response_times": {
                "min_ms": min(response_times)*1000 if response_times else 0,
                "max_ms": max(response_times)*1000 if response_times else 0,
                "mean_ms": statistics.mean(response_times)*1000 if response_times else 0,
                "p50_ms": response_times[int(len(response_times)*0.50)]*1000 if response_times else 0,
                "p90_ms": response_times[int(len(response_times)*0.90)]*1000 if response_times else 0,
                "p95_ms": response_times[int(len(response_times)*0.95)]*1000 if response_times else 0,
                "p99_ms": response_times[int(len(response_times)*0.99)]*1000 if response_times else 0,
            },
            "container_metrics": container_metrics if container_metrics else {},
            "status_codes": dict(self.results["status_codes"]),
            "errors": dict(self.results["errors"]),
        }

        with open(results_file, 'w') as f:
            json.dump(results_data, f, indent=2)

        print(f"\nResults saved to: {results_file}\n")


async def main():
    """Main test execution"""

    # Test scenarios: (endpoint, method, json_data, weight)
    # Focus on /shop, /product/id, and /purchase as requested
    scenarios = [
        ("/shop", "GET", None, 0.40),  # 40% shop page (4000 requests)
        ("/product/1", "GET", None, 0.20),  # 20% product page 1 (2000 requests)
        ("/product/2", "GET", None, 0.15),  # 15% product page 2 (1500 requests)
        ("/product/3", "GET", None, 0.10),  # 10% product page 3 (1000 requests)
        ("/purchase", "POST", {"product_id": 1, "quantity": 1}, 0.10),  # 10% purchases (1000 requests)
        ("/purchase", "POST", {"product_id": 2, "quantity": 1}, 0.05),  # 5% purchases (500 requests)
    ]

    print("""
================================================================================
                    E-COMMERCE LOAD TEST
                    10,000 Concurrent Requests
================================================================================
    """)

    print("Test Scenarios:")
    print(f"{'Endpoint':<30} {'Method':<8} {'Requests':<10} {'Weight':<10}")
    print("-" * 80)
    for endpoint, method, data, weight in scenarios:
        count = int(10000 * weight)
        print(f"{endpoint:<30} {method:<8} {count:<10} {weight*100:.0f}%")

    print("\nMetrics to be collected:")
    print("  - Latency: p50, p90, p95, p99")
    print("  - Application CPU Usage (per Python process)")
    print("  - Application RAM Usage (per Python process)")
    print("  - Request rate and success/failure rates")
    print("\nNote: Metrics are for application processes only, not whole device")

    input("\nPress ENTER to start the load test...")

    tester = LoadTester(
        base_url="http://localhost:8000",
        total_requests=10000,
        concurrent_workers=100,
        prometheus_url="http://localhost:9090"
    )

    await tester.run_test(scenarios)

    print("\nTIP: Check Grafana dashboard at http://localhost:3000 to see real-time metrics!")
    print("     Look for spikes in CPU, memory, and latency during the test.\n")


if __name__ == "__main__":
    asyncio.run(main())

