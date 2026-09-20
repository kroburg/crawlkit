"""DNS pinning, including the IPv6 case a naive split silently mangles."""

import pytest

from crawlkit import resolverules


def test_ipv4_entry():
    assert resolverules.rules(["example.test:1.2.3.4"]) == "MAP example.test 1.2.3.4"


def test_bracketed_ipv6_entry_survives():
    """`entry.split(':')[1]` turned this into '[' and pinned nothing."""
    assert resolverules.rules(["example.test:[::1]"]) == "MAP example.test [::1]"


def test_bare_ipv6_entry_is_accepted_and_bracketed():
    assert resolverules.rules(["example.test:2001:db8::5"]) == "MAP example.test [2001:db8::5]"


def test_multiple_entries_are_comma_joined():
    assert (
        resolverules.rules(["a.test:1.2.3.4", "b.test:[::1]"])
        == "MAP a.test 1.2.3.4,MAP b.test [::1]"
    )


def test_no_entries_means_no_flag():
    assert resolverules.rules([]) is None
    assert resolverules.launch_args(None) == []


def test_launch_args_shape():
    assert resolverules.launch_args(["a.test:1.2.3.4"]) == [
        "--host-resolver-rules=MAP a.test 1.2.3.4"
    ]


@pytest.mark.parametrize(
    "bad", ["example.test", "example.test:", ":1.2.3.4", "example.test:not-an-ip"]
)
def test_malformed_entries_are_rejected_loudly(bad):
    with pytest.raises(ValueError):
        resolverules.rules([bad])
