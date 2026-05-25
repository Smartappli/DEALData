"""Tests for authentication helpers."""

from auth.tokens import TOKEN_DIGEST_LENGTH, generate_url_token, hash_url_token


def test_generate_url_token_returns_distinct_url_safe_tokens() -> None:
    first_token = generate_url_token()
    second_token = generate_url_token()

    assert first_token != second_token
    assert "/" not in first_token
    assert "+" not in first_token
    assert "=" not in first_token


def test_hash_url_token_is_stable_and_does_not_store_plaintext() -> None:
    token = generate_url_token()

    first_digest = hash_url_token(token)
    second_digest = hash_url_token(token)

    assert first_digest == second_digest
    assert first_digest != token
    assert len(first_digest) == TOKEN_DIGEST_LENGTH
