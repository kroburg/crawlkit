"""Pacing and resumability, with time injected so the suite stays fast."""

import random
import subprocess

from crawlkit import drive, rawstore


class FakeRun:
    """Stands in for subprocess.run: scripted outcomes per invocation."""

    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.calls = []

    def __call__(self, command, timeout=None, capture_output=None, text=None):
        self.calls.append((command, timeout))
        outcome = self.outcomes.pop(0) if self.outcomes else 0
        if outcome == "timeout":
            raise subprocess.TimeoutExpired(command, timeout)
        return subprocess.CompletedProcess(command, outcome, "", "")


def sleeps():
    recorded = []
    return recorded, recorded.append


def test_a_finished_item_is_skipped_without_fetch_or_sleep(tmp_path):
    rawstore.write_parsed(tmp_path, "a", {"ok": True})
    run = FakeRun([])
    slept, sleep = sleeps()

    summary = drive.harvest_all(["a"], lambda item: ["echo"], tmp_path, sleep=sleep, run=run)

    assert summary["skipped"] == ["a"] and summary["done"] == []
    assert run.calls == [] and slept == []


def test_an_empty_sentinel_is_retried_not_trusted(tmp_path):
    rawstore.sentinel_path(tmp_path, "a").parent.mkdir(parents=True, exist_ok=True)
    rawstore.sentinel_path(tmp_path, "a").write_text("")
    run = FakeRun([0])
    _, sleep = sleeps()

    summary = drive.harvest_all(["a"], lambda item: ["echo"], tmp_path, sleep=sleep, run=run)
    assert summary["done"] == ["a"]


def test_failures_retry_three_times_with_flat_backoff(tmp_path):
    run = FakeRun([1, 1, 0])
    slept, sleep = sleeps()

    summary = drive.harvest_all(
        ["a"], lambda item: ["echo"], tmp_path, backoff_s=30, sleep=sleep, run=run
    )
    assert summary["done"] == ["a"]
    assert len(run.calls) == 3
    assert slept == [30, 30], "flat, not exponential"


def test_a_hung_attempt_is_killed_and_counted_as_a_failure(tmp_path):
    run = FakeRun(["timeout", "timeout", "timeout"])
    _, sleep = sleeps()

    summary = drive.harvest_all(
        ["a"], lambda item: ["echo"], tmp_path, backoff_s=0, sleep=sleep, run=run
    )
    assert summary["failed"] == ["a"]
    assert all(timeout == drive.ATTEMPT_TIMEOUT_S for _, timeout in run.calls)


def test_one_failure_does_not_abort_the_rest_of_the_list(tmp_path):
    run = FakeRun([1, 1, 1, 0])
    _, sleep = sleeps()

    summary = drive.harvest_all(
        ["a", "b"], lambda item: ["echo"], tmp_path, backoff_s=0, sleep=sleep, run=run
    )
    assert summary["failed"] == ["a"] and summary["done"] == ["b"]


def test_spacing_is_jittered_within_the_band_and_not_a_metronome(tmp_path):
    run = FakeRun([0] * 8)
    slept, sleep = sleeps()

    drive.harvest_all(
        [str(i) for i in range(8)],
        lambda item: ["echo"],
        tmp_path,
        sleep=sleep,
        run=run,
        rng=random.Random(4),
    )
    assert len(slept) == 7, "no pause before the first item"
    assert all(11 <= gap <= 15 for gap in slept), slept
    assert len(set(round(gap, 3) for gap in slept)) > 1, "a constant interval is a signature"


def test_pacing_is_skipped_for_items_that_need_no_fetch(tmp_path):
    rawstore.write_parsed(tmp_path, "b", {"ok": True})
    run = FakeRun([0, 0])
    slept, sleep = sleeps()

    drive.harvest_all(["a", "b", "c"], lambda item: ["echo"], tmp_path, sleep=sleep, run=run)
    assert len(slept) == 1, "only the gap between the two real fetches"


def test_events_narrate_what_happened(tmp_path):
    run = FakeRun([1, 0])
    _, sleep = sleeps()
    events = []

    drive.harvest_all(
        ["a"],
        lambda item: ["echo"],
        tmp_path,
        backoff_s=0,
        sleep=sleep,
        run=run,
        on_event=lambda name, data: events.append(name),
    )
    assert events == ["fetching", "attempt_failed", "done"]
