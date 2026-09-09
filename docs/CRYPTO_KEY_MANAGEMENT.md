# Cryptographic Key Management

## Keys

Separate:
- vault encryption keys
- certificate signing keys
- authentication/session secrets

## Vault

Use authenticated encryption via a vetted library.

Store only a key reference in normal database records.

## Signing

Protect signing keys from ordinary API access.

Use a vetted Ed25519 implementation where appropriate.

## Development

Development keys must never be reused in production.

Never commit secrets.

Never log:
- private keys
- vault keys
- plaintext recovery secrets

## Rotation

Design key references so keys can be rotated without invalidating historical verification.
Historical certificates must retain enough metadata to identify the correct verification key.
