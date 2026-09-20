"""Rate limiting by structure instead of by lock.

Bucket the URLs by host, hand each whole bucket to one worker, and sleep
between hits inside a bucket. Two requests can then never land on the same
server at once — not because a limiter forbids it, but because there is only
one thread that could issue them. No shared counters, no token bucket, nothing
to get wrong under concurrency.
"""

import time
import urllib.parse
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor

from crawlkit import contract

PER_HOST_INTERVAL_S = contract.get("http.per_host_interval_s")
MAX_PARALLEL_HOSTS = contract.get("http.max_parallel_hosts")


def host_of(url):
    return (urllib.parse.urlsplit(url).hostname or "").lower()


def bucket_by_host(urls):
    buckets = defaultdict(list)
    for url in urls:
        buckets[host_of(url)].append(url)
    return dict(buckets)


def run_host_serial(urls, work, interval_s=None, sleep=time.sleep, on_result=None):
    interval = PER_HOST_INTERVAL_S if interval_s is None else interval_s
    results = []
    for index, url in enumerate(urls):
        if index:
            sleep(interval)
        outcome = work(url)
        if on_result:
            on_result(url, outcome)
        results.append((url, outcome))
    return results


def run(urls, work, interval_s=None, max_hosts=None, sleep=time.sleep, on_result=None):
    """Parallel across hosts, serial within a host. Returns [(url, outcome)]."""
    buckets = bucket_by_host(urls)
    if not buckets:
        return []
    workers = min(max_hosts or MAX_PARALLEL_HOSTS, len(buckets))
    collected = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        batches = pool.map(
            lambda group: run_host_serial(group, work, interval_s, sleep, on_result),
            buckets.values(),
        )
        for batch in batches:
            collected.extend(batch)
    return collected
