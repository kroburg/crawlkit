"""Parallel across hosts, serial within a host — observed, not assumed."""

import time
from collections import defaultdict

from crawlkit import schedule


def test_urls_are_bucketed_by_hostname_case_insensitively():
    buckets = schedule.bucket_by_host(
        ["http://A.test/1", "http://a.test/2", "https://b.test/3", "http://a.test:8080/4"]
    )
    assert sorted(buckets) == ["a.test", "b.test"]
    assert len(buckets["a.test"]) == 3


def test_one_host_is_hit_serially_with_the_interval_between_hits():
    gaps = []
    schedule.run(
        [f"http://one.test/{i}" for i in range(4)],
        work=lambda url: 200,
        interval_s=0.05,
        sleep=lambda seconds: gaps.append(seconds),
    )
    assert gaps == [0.05, 0.05, 0.05], "no sleep before the first hit, one before each other"


def test_distinct_hosts_run_concurrently(fixture_port, named_hosts):
    """Wall time tracks the slowest host, not the sum of all hosts."""
    urls = [
        f"http://{h}:{fixture_port}/hostlog?work=0.4"
        for h in ("alpha.test", "beta.test", "gamma.test")
    ]
    started = time.monotonic()
    results = schedule.run(urls, work=lambda url: _status(url), interval_s=0)
    elapsed = time.monotonic() - started
    assert len(results) == 3
    assert elapsed < 1.0, f"hosts appear serialized: {elapsed:.2f}s for 3 x 0.4s"


def test_requests_to_one_host_never_overlap(fixture_port, named_hosts):
    """The structural guarantee: one bucket, one worker, so no interleaving."""
    active = defaultdict(int)
    overlaps = []

    def work(url):
        host = schedule.host_of(url)
        active[host] += 1
        if active[host] > 1:
            overlaps.append(host)
        time.sleep(0.05)
        active[host] -= 1
        return 200

    urls = [f"http://alpha.test/{i}" for i in range(5)] + [
        f"http://beta.test/{i}" for i in range(5)
    ]
    schedule.run(urls, work=work, interval_s=0)
    assert not overlaps


def test_empty_input_is_not_an_error():
    assert schedule.run([], work=lambda url: 200) == []


def _status(url):
    import urllib.request

    with urllib.request.urlopen(url, timeout=10) as resp:
        return resp.status
