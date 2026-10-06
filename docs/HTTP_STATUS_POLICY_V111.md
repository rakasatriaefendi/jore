# HTTP status handling used by JORE v1.11.0

The classifier covers the status codes supplied for the project. JORE does not
blindly retry every HTTP error.

| Family / codes | JORE handling |
|---|---|
| 1xx, 2xx, 3xx | not treated as provider failure by themselves |
| 400 | bad request; no automatic provider retry |
| 401 / 407 | authentication problem; stable fingerprint, no cooldown retry |
| 402 | billing/payment problem; no automatic retry |
| 403 / 451 | permission/legal access problem; no automatic retry |
| 404 / 410 | missing resource; no automatic retry |
| 405/406/411/412/413/414/415/416/417/421/422/423/424/426/428/431 | request-contract problem; no blind retry |
| 408 | transient timeout; cooldown, no retry-budget consumption |
| 409 | conflict; retryable but counts as a task retry |
| 425 | transient/too early; short cooldown |
| 429 | rate limit; honors numeric `Retry-After` when present; no retry-budget consumption |
| 500 | transient server error; cooldown |
| 501 / 505 / 506 / 510 | server capability/config issue; no blind retry |
| 502 | bad gateway; cooldown |
| 503 | service unavailable; cooldown |
| 504 | gateway timeout; cooldown |
| 507 | provider/storage capacity; cooldown |
| 508 | loop detected; do not retry blindly |
| 511 | network authentication required; no automatic retry |

Text-only provider errors such as `rate limit`, `quota exceeded`, `timed out`,
`connection reset`, `connection refused`, and `network unreachable` are also
classified when no explicit HTTP status is present.
