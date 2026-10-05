# Security Policy for SkyPulse

The SkyPulse team is committed to maintaining a secure and reliable meteorological big data platform.

---

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 1.0.x   | :white_check_mark: |
| < 1.0   | :x:                |

---

## Reporting a Vulnerability

If you discover a security vulnerability within SkyPulse:

1. **Do NOT open a public GitHub issue.**
2. Send a detailed report privately to the maintainers or repository owner.
3. Include the following details in your report:
   - Description of the vulnerability and its potential impact
   - Step-by-step instructions or proof-of-concept (PoC) to reproduce the issue
   - Affected components (Backend API, Ingestion Connectors, Authentication, WebSocket, etc.)
   - Suggested mitigation or fix, if known

### Response Timeline
- **Acknowledgment**: Within 48 hours
- **Assessment & Mitigation Plan**: Within 7 business days
- **Fix & Advisory Release**: Coordinated with the reporter prior to public disclosure

---

## Security Practices in SkyPulse

- **Secret Management**: Real credentials (API keys, JWT secrets, database passwords, service account JSON files) must never be committed to source control. Always use environment variables loaded via `.env` files (excluded by `.gitignore`).
- **Input Sanitization & Injection Defense**: All user reports and external webhook inputs are validated using Pydantic schemas and parameterized database queries to prevent SQL and NoSQL injections.
- **Redaction Pipeline**: The ingestion engine automatically redacts credentials, access keys, and PII patterns before indexing or storing news feeds and social signals.
- **Rate Limiting & Authentication**: Administrative endpoints and write operations require JWT authentication and adhere to role-based access control (RBAC).
