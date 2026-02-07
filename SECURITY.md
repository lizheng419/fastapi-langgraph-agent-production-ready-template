# Security Policy

## Reporting a Vulnerability

If you discover a security vulnerability, please report it responsibly by opening a private issue or contacting the project maintainers directly. Do **not** disclose vulnerabilities in public issues.

## Security Architecture

### Authentication & Sessions

- **JWT tokens** for stateless authentication with configurable expiration
- Session-based user management with per-session isolation
- Passwords hashed with bcrypt before storage
- All protected endpoints use `get_current_session` dependency injection

### Environment & Secrets

- All secrets (`JWT_SECRET_KEY`, `OPENAI_API_KEY`, `LANGFUSE_SECRET_KEY`, database credentials) must be stored in environment variables or `.env` files
- `.env` files are gitignored — never commit secrets to version control
- Docker Compose passes secrets via `env_file` and `environment` directives
- `docker-entrypoint.sh` validates required secrets on startup and exits if missing

### Rate Limiting

- All API endpoints are rate-limited via `slowapi` decorators
- Configurable per-endpoint limits (e.g., `30/minute` for chat, `5/minute` for auth)
- Rate limiting is enabled by default (`RATE_LIMIT_ENABLED=true`)

### CORS

- CORS origins are configurable via `CORS_ORIGINS` environment variable
- Default configuration restricts to known frontend origins
- Credentials, methods, and headers are explicitly allowlisted

### Human-in-the-Loop (HITL)

- Sensitive tool calls (delete, modify, execute_sql, send_email) are intercepted before execution
- Approval requests require explicit user approve/reject action
- Unapproved requests expire after a configurable timeout

### Docker Security

- Application runs as non-root user (`appuser`) inside containers
- Secrets are never baked into Docker images
- Database credentials are injected at runtime via environment variables
- PostgreSQL healthcheck ensures DB readiness before app starts

### Input Validation

- All request payloads validated with Pydantic v2 models
- SQL injection mitigated by SQLModel/SQLAlchemy ORM (no raw queries)
- User inputs sanitized before processing

### Observability

- Structured logging with `structlog` — no secrets logged
- Langfuse tracing for LLM call auditing
- Prometheus metrics for anomaly detection

## Best Practices for Deployment

1. Use strong, unique values for `JWT_SECRET_KEY` (min 32 characters)
2. Rotate API keys periodically
3. Enable HTTPS in production (terminate TLS at reverse proxy)
4. Restrict database access to application network only
5. Review and update rate limiting rules for production traffic
6. Set `DEBUG=false` in production environments
7. Regularly update dependencies for security patches

