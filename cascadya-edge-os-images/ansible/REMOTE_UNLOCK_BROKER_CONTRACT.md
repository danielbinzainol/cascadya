# Remote Unlock Broker Contract

This repository only implements the IPC-side remote unlock flow.
The broker and Vault remain external services.

## Transport assumptions

- The IPC reaches the broker through `wg-quick@wg0`.
- All broker calls use mTLS with:
  - `client.crt`
  - `client.key`
  - `ca.crt`
- The IPC sends TPM quote material tied to the configured PCR set.

## Endpoint: `POST /challenge`

### Request body

```json
{
  "device_id": "ipc-001",
  "hostname": "cascadya",
  "wg_interface": "wg0",
  "gateway_mac": "aa:bb:cc:dd:ee:ff"
}
```

Notes:

- `gateway_mac` is optional.
- `gateway_mac` is telemetry only. It must not be used as an authorization factor.

### Success response

```json
{
  "challenge_id": "b3b5a5b8-8f0b-4c6a-a24d-91b6c6d63fdf",
  "nonce": "base64-or-opaque-challenge"
}
```

## Endpoint: `POST /unlock`

### Request body

```json
{
  "device_id": "ipc-001",
  "challenge_id": "b3b5a5b8-8f0b-4c6a-a24d-91b6c6d63fdf",
  "nonce": "base64-or-opaque-challenge",
  "hostname": "cascadya",
  "wg_interface": "wg0",
  "quote_b64": "<base64>",
  "signature_b64": "<base64>",
  "pcr_b64": "<base64>",
  "ak_pub_b64": "<base64>",
  "gateway_mac": "aa:bb:cc:dd:ee:ff"
}
```

### Success response

```json
{
  "secret_b64": "<base64-luks-secret>"
}
```

### Refusal response

```json
{
  "error": "unlock_denied",
  "reason": "tpm_quote_verification_failed"
}
```

## Broker responsibilities

- Verify the boot mTLS client certificate.
- Map the certificate to the expected device identity.
- Verify the TPM attestation key or persistent handle registration for the device.
- Verify the TPM quote against the server-issued nonce and the expected PCR set.
- Fetch the device-specific LUKS secret from Vault.
- Return the secret only when both mTLS identity and TPM attestation are valid.
- Log:
  - certificate fingerprint
  - device ID
  - hostname
  - source WireGuard IP
  - challenge ID
  - decision
  - refusal reason
  - gateway MAC if present

## Security notes

- The broker must treat the router MAC as context only.
- The broker should expire or one-time-bind challenges.
- The broker should never persist the decoded LUKS secret in application logs.
- The IPC-side fallback remains the manual passphrase helper.
