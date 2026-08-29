"""One-off helper: generate an API key for the /api/gpt/* Custom GPT Action.

Usage:
    python -m app.backend.scripts.generate_gpt_api_key

Prints the raw key (paste into the Custom GPT's Action authentication, once —
it is not stored anywhere) and its SHA-256 hash (paste into the GPT_API_KEY_HASH
environment variable on Railway). Re-run this script and update the env var to
rotate the key.
"""
import hashlib
import secrets


def main() -> None:
    key = secrets.token_urlsafe(32)
    key_hash = hashlib.sha256(key.encode("utf-8")).hexdigest()
    print("API key (paste once into the Custom GPT Action's API Key auth):")
    print(f"  {key}")
    print()
    print("GPT_API_KEY_HASH (paste into Railway's environment variables):")
    print(f"  {key_hash}")


if __name__ == "__main__":
    main()
