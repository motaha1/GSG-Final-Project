"""
Load Testing Script for E-Commerce Application
Tests performance under high concurrent load (10,000 requests)
"""
import asyncio
import aiohttp
import time
from datetime import datetime
from collections import defaultdict
import json
import statistics


class LoadTester:
    def __init__(self, base_url="http://localhost:8000", total_requests=10000, concurrent_workers=100):
        self.base_url = base_url
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
        print(f"🚀 LOAD TEST STARTED")
        print(f"{'='*80}")
        print(f"Base URL: {self.base_url}")
        print(f"Total Requests: {self.total_requests:,}")
        print(f"Concurrent Workers: {self.concurrent_workers}")
        print(f"Test Scenarios: {len(scenarios)}")
        print(f"{'='*80}\n")

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

        # Calculate statistics
        self.print_results(total_time)

    def print_results(self, total_time):
        """Print detailed test results"""
        print(f"\n{'='*80}")
        print(f"📊 LOAD TEST RESULTS")
        print(f"{'='*80}\n")

        # Summary
        print("SUMMARY:")
        print(f"  Total Time: {total_time:.2f} seconds")
        print(f"  Total Requests: {self.total_requests:,}")
        print(f"  Successful: {self.results['successful']:,} ({self.results['successful']/self.total_requests*100:.1f}%)")
        print(f"  Failed: {self.results['failed']:,} ({self.results['failed']/self.total_requests*100:.1f}%)")
        print(f"  Timeouts: {self.results['timeouts']:,} ({self.results['timeouts']/self.total_requests*100:.1f}%)")
        print(f"  Requests/sec: {self.total_requests/total_time:.2f}")

        # Response times
        if self.results["response_times"]:
            response_times = sorted(self.results["response_times"])
            print(f"\nRESPONSE TIMES:")
            print(f"  Min: {min(response_times)*1000:.2f} ms")
            print(f"  Max: {max(response_times)*1000:.2f} ms")
            print(f"  Mean: {statistics.mean(response_times)*1000:.2f} ms")
            print(f"  Median (p50): {statistics.median(response_times)*1000:.2f} ms")
            print(f"  p95: {response_times[int(len(response_times)*0.95)]*1000:.2f} ms")
            print(f"  p99: {response_times[int(len(response_times)*0.99)]*1000:.2f} ms")

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
        with open(results_file, 'w') as f:
            json.dump({
                "total_time": total_time,
                "total_requests": self.total_requests,
                "successful": self.results["successful"],
                "failed": self.results["failed"],
                "timeouts": self.results["timeouts"],
                "requests_per_second": self.total_requests/total_time,
                "response_times": {
                    "min_ms": min(self.results["response_times"])*1000 if self.results["response_times"] else 0,
                    "max_ms": max(self.results["response_times"])*1000 if self.results["response_times"] else 0,
                    "mean_ms": statistics.mean(self.results["response_times"])*1000 if self.results["response_times"] else 0,
                    "median_ms": statistics.median(self.results["response_times"])*1000 if self.results["response_times"] else 0,
                    "p95_ms": sorted(self.results["response_times"])[int(len(self.results["response_times"])*0.95)]*1000 if self.results["response_times"] else 0,
                    "p99_ms": sorted(self.results["response_times"])[int(len(self.results["response_times"])*0.99)]*1000 if self.results["response_times"] else 0,
                },
                "status_codes": dict(self.results["status_codes"]),
                "errors": dict(self.results["errors"]),
            }, f, indent=2)

        print(f"\n✅ Results saved to: {results_file}\n")


async def main():
    """Main test execution"""

    # Test scenarios: (endpoint, method, json_data, weight)
    scenarios = [
        ("/health", "GET", None, 0.20),  # 20% health checks
        ("/products", "GET", None, 0.30),  # 30% list products
        ("/stock?product_id=1", "GET", None, 0.25),  # 25% check stock
        ("/stock?product_id=2", "GET", None, 0.15),  # 15% check stock
        ("/purchase", "POST", {"product_id": 1, "quantity": 1}, 0.10),  # 10% purchases
    ]

    print("""
╔══════════════════════════════════════════════════════════════════════════╗
║                    E-COMMERCE LOAD TEST                                  ║
║                    10,000 Concurrent Requests                            ║
╚══════════════════════════════════════════════════════════════════════════╝
    """)

    print("Test Scenarios:")
    for endpoint, method, data, weight in scenarios:
        count = int(10000 * weight)
        print(f"  • {method:6} {endpoint:30} {count:5} requests ({weight*100:.0f}%)")

    input("\nPress ENTER to start the load test...")

    tester = LoadTester(
        base_url="http://localhost:8000",
        total_requests=10000,
        concurrent_workers=100
    )

    await tester.run_test(scenarios)

    print("\n💡 TIP: Check Grafana dashboard at http://localhost:3000 to see metrics!")
    print("   Look for spikes in CPU, memory, and latency during the test.\n")


if __name__ == "__main__":
    asyncio.run(main())

