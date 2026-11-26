"""Authentication challenge parsing shared by synchronous and asynchronous clients."""

import pytest

from caldav.lib.auth import extract_auth_types, select_auth_type


@pytest.mark.parametrize(
    "header, expected",
    [
        ('Bearer realm="x", error_description="expired, basic auth not accepted"', {"bearer"}),
        ('Digest realm="x", qop="auth,auth-int", nonce="abc"', {"digest"}),
        ('Digest realm="x", qop="auth,auth-int", Basic realm="fallback"', {"digest", "basic"}),
        ('Bearer realm="x", error = "invalid_token", scope="calendar"', {"bearer"}),
        ('Bearer realm="x", error_description="escaped \\"quote, Basic fake"', {"bearer"}),
        ('Negotiate YWJjZA==, Basic realm="x"', {"negotiate", "basic"}),
        ('Basic, dIGEST realm="test",', {"basic", "digest"}),
        ("", set()),
    ],
)
def test_extract_auth_challenges(header, expected):
    assert extract_auth_types(header) == expected


def test_bearer_description_does_not_enable_password_auth():
    schemes = extract_auth_types(
        'Bearer realm="x", error_description="expired, basic auth not accepted"'
    )
    assert select_auth_type(schemes, has_username=True, has_password=True) is None
    assert select_auth_type(schemes, has_username=False, has_password=True) == "bearer"
