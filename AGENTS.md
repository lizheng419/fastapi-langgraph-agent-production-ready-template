# AI Agent Development Guide

This document provides essential guidelines for AI agents working on this LangGraph FastAPI Agent project.

## Project Overview

This is a production-ready AI agent application built with:
- **LangGraph** for stateful, multi-step AI agent workflows
- **FastAPI** for high-performance async REST API endpoints
- **Langfuse** for LLM observability and tracing
- **PostgreSQL + pgvector** for long-term memory storage (mem0ai)
- **JWT authentication** with session management
- **Prometheus + Grafana** for monitoring
- **Skills** progressive disclosure system with **SkillCreator** auto-generation
- **MCP** (Model Context Protocol) for external tool integration
- **HITL** (Human-in-the-Loop) approval system for sensitive operations
- **Workflow Engine** for multi-step orchestrated workflows
- **V1 Agent** with composable Middleware stack
- **RAG** pluggable knowledge base retrieval (Qdrant, pgvector, RAGFlow, Dify, FastGPT, custom HTTP)
- **RAG Document Ingestion** — frontend upload → PDF/TXT/MD/DOCX parsing → chunking → embedding → Qdrant storage
- **Qdrant** vector database for RAG integration
- **React Frontend** with agent mode selector, knowledge base management, and i18n

## Quick Reference: Critical Rules

### Import Rules
- **All imports MUST be at the top of the file** - never add imports inside functions or classes

### Logging Rules
- Use **structlog** for all logging
- Log messages must be **lowercase_with_underscores** (e.g., `"user_login_successful"`)
- **NO f-strings in structlog events** - pass variables as kwargs
- Use `logger.exception()` instead of `logger.error()` to preserve tracebacks
- Example: `logger.info("chat_request_received", session_id=session.id, message_count=len(messages))`

### Retry Rules
- **Always use tenacity library** for retry logic
- Configure with exponential backoff
- Example: `@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))`

### Output Rules
- **Always enable rich library** for formatted console outputs
- Use rich for progress bars, tables, panels, and formatted text

### Caching Rules
- **Only cache successful responses**, never cache errors
- Use appropriate cache TTL based on data volatility

### FastAPI Rules
- All routes must have rate limiting decorators
- Use dependency injection for services, database connections, and auth
- All database operations must be async

## Code Style Conventions

### Python/FastAPI
- Use `async def` for asynchronous operations
- Use type hints for all function signatures
- Prefer Pydantic models over raw dictionaries
- Use functional, declarative programming; avoid classes except for services and agents
- File naming: lowercase with underscores (e.g., `user_routes.py`)
- Use the RORO pattern (Receive an Object, Return an Object)

### Error Handling
- Handle errors at the beginning of functions
- Use early returns for error conditions
- Place the happy path last in the function
- Use guard clauses for preconditions
- Use `HTTPException` for expected errors with appropriate status codes

### Frontend (React)
- Use functional components with hooks
- Keep API calls in `frontend/src/api.js`
- Use `useLanguage()` hook for i18n — add keys to both `zh.json` and `en.json`
- Use TailwindCSS for styling; Lucide React for icons
- Agent mode state is managed via `localStorage` + React state in `ChatPage.jsx`

## Agent Architecture

### Four Agent Modes

| Mode | Implementation | API Prefix | Key Class |
|------|---------------|------------|-----------|
| Single | `create_agent` + Middleware | `/chatbot` | `V1Agent` |
| Multi | Supervisor + Workers | `/chatbot?mode=multi` | `V1MultiAgent` |
| Workflow | Orchestrator-Worker + Send | `/chatbot/workflow` | `WorkflowGraph` |

### V1 Middleware Stack
Located in `app/core/langgraph/v1/middleware.py` (follows official [Context Engineering](https://docs.langchain.com/oss/python/langchain/context-engineering) guide):
- `@dynamic_prompt skills_aware_prompt` — dynamic system prompt with Skills + long-term memory
- `SummarizationMiddleware` — auto-condense long conversation history (built-in, configurable via `SUMMARIZATION_*` env vars)
- `@wrap_model_call role_based_tool_filter` (async) — dynamic tool selection by user role
- `LangfuseTracingMiddleware` — auto Langfuse callback + async tool passthrough
- `MetricsMiddleware` — Prometheus histogram timing + async tool passthrough
- `HITLApprovalMiddleware` — sensitive tool interception (sync + async)

**Important async rule**: All `AgentMiddleware` subclasses MUST provide both sync and async versions of `wrap_model_call`/`wrap_tool_call` (i.e., also implement `awrap_model_call`/`awrap_tool_call`), because the agent uses `astream()`/`ainvoke()`. Failing to do so causes `NotImplementedError` at runtime.

### Workflow Engine
Located in `app/core/langgraph/workflow/`:
- `WorkflowPlanner` — YAML template matching + LLM dynamic planning
- `WorkflowGraph` — Orchestrator-Worker pattern with `Send` API
- Templates in `workflow/templates/*.yaml`
- Add new templates as YAML files; auto-loaded on startup

## Skills System

### Progressive Disclosure
- Skills are markdown files in `app/core/skills/prompts/`
- Only brief descriptions appear in system prompt
- Full content loaded on-demand via `load_skill` tool

### SkillCreator
- `app/core/skills/creator.py` — LLM-driven skill auto-creation
- Agent tools: `create_skill`, `update_skill`, `list_all_skills`
- Auto-generated skills persist to `app/core/skills/prompts/_auto/`
- Schema includes `version`, `source`, `auto_generated`, `created_at`, `updated_at`

### Adding Skills Manually
Create a markdown file in `app/core/skills/prompts/`:
```markdown
---
name: my_skill
description: Brief description for system prompt
tags: tag1, tag2
---
Full skill content loaded on-demand...
```

## RAG Knowledge Base Integration

Located in `app/core/rag/`:
- **Pluggable provider architecture** — `BaseRetriever` interface + `RetrieverManager` registry
- **Built-in providers**: Qdrant, pgvector, RAGFlow, GenericHTTP (Dify/FastGPT/custom)
- **Configuration**: `rag_providers.json` at project root (mounted into Docker container)
- **Agent tool**: `retrieve_knowledge` — searches across all enabled providers, merges and deduplicates results
- **Provider-agnostic document management**: `BaseRetriever` defines `list_documents`, `get_document_chunks`, `delete_document`; `RetrieverManager` aggregates across providers
- **Shared singleton**: `get_shared_manager()` in `manager.py` — API routes and agent tools share one `RetrieverManager` instance
- **Adding a new provider**: Implement `BaseRetriever` in `app/core/rag/providers/`, register in `PROVIDER_REGISTRY`

### Supported Providers

| Provider | Type | Use Case |
|----------|------|----------|
| `QdrantRetriever` | `qdrant` | Local Qdrant vector DB |
| `PgvectorRetriever` | `pgvector` | Shared PostgreSQL pgvector |
| `RAGFlowRetriever` | `ragflow` | External RAGFlow (dataset retrieval + OpenAI-compatible chat) |
| `GenericHTTPRetriever` | `http` | Any REST API (Dify, FastGPT, custom systems) |

### RAG Document Ingestion

Located in `app/core/rag/ingest.py`:
- **Pipeline**: Frontend upload → parse (PDF/TXT/MD/DOCX) → chunk (1000 chars, 200 overlap) → embed → Qdrant upsert
- **Ingestion only** in `app/core/rag/ingest.py` — document listing/chunks/delete moved to `BaseRetriever` providers
- **API routes**: `app/api/v1/rag.py` — `POST /upload`, `GET /documents`, `DELETE /documents/{doc_id}` (uses `get_shared_manager()`)
- **Frontend**: `KnowledgePage.jsx` at `/knowledge` — drag-and-drop upload, document list with chunk viewer, delete (with `provider` param)
- **Embedding**: Reuses `LONG_TERM_MEMORY_EMBEDDER_MODEL` / `LONG_TERM_MEMORY_EMBEDDER_DIMS` from `.env`
- **Dependencies**: `pypdf`, `python-docx`, `langchain-text-splitters`

## MCP Integration

- Configuration: `mcp_servers.json` (streamable_http, SSE, and stdio transports)
- Client: `app/core/mcp/client.py` — `MCPManager` wraps `MultiServerMCPClient` with persistent sessions
- Tools auto-discovered at agent startup via `_initialize_mcp_tools()`
- Graceful cleanup: `mcp_manager.close()` called in FastAPI lifespan shutdown

## Human-in-the-Loop (HITL)

- `app/core/langgraph/hitl/` — ApprovalManager + approval_check node
- Sensitive patterns: `delete`, `modify`, `update`, `write`, `execute_sql`, `send_email`
- REST API: `/api/v1/approvals/*`
- Frontend: `ApprovalsPage.jsx`

## LangGraph & LangChain Patterns

### Graph Structure
- Use `StateGraph` for building AI agent workflows
- Define clear state schemas using Pydantic models (see `app/schemas/`)
- Use `CompiledStateGraph` for production workflows
- Implement `AsyncPostgresSaver` for checkpointing and persistence
- Use `Command` for controlling graph flow between nodes

### Tracing
- Use LangChain's `CallbackHandler` from Langfuse for tracing all LLM calls
- All LLM operations must have Langfuse tracing enabled

### Memory (mem0ai)
- Use `AsyncMemory` for semantic memory storage
- Store memories per user_id for personalized experiences
- Use async methods: `add()`, `get()`, `search()`, `delete()`
- Configure embedding dimensions via `LONG_TERM_MEMORY_EMBEDDER_DIMS` (e.g., 768 for `bge-base-zh-v1.5`, 1536 for OpenAI)
- Always use `await agent.aget_state()` instead of sync `agent.get_state()` when using `AsyncPostgresSaver`

## Authentication & Security

- Use JWT tokens for authentication
- Implement session-based user management (see `app/api/v1/auth.py`)
- Use `get_current_session` dependency for protected endpoints
- Store sensitive data in environment variables
- Validate all user inputs with Pydantic models

## Database Operations

- Use SQLModel for ORM models (combines SQLAlchemy + Pydantic)
- Define models in `app/models/` directory
- Use async database operations with asyncpg
- Use LangGraph's AsyncPostgresSaver for agent checkpointing
- Schema: `schema.sql` (PostgreSQL with pgvector)

## Performance Guidelines

- Minimize blocking I/O operations
- Use async for all database and external API calls
- Implement caching for frequently accessed data
- Use connection pooling for database connections
- Optimize LLM calls with streaming responses

## Observability

- Integrate Langfuse for LLM tracing on all agent operations
- Export Prometheus metrics for API performance
- Use structured logging with context binding (request_id, session_id, user_id)
- Track LLM inference duration, token usage, and costs

## Testing & Evaluation

- Unit tests in `tests/` — Skills, MCP, integration tests
- Metric-based evaluations in `evals/` with Langfuse traces
- Custom evaluation metrics as markdown files in `evals/metrics/prompts/`
- Run tests: `uv run pytest`
- Run evaluations: `make eval`

## Configuration Management

- Use `.env` for all environment configuration (copy from `.env.example`)
- Use Pydantic Settings for type-safe configuration (see `app/core/config.py`)
- Never hardcode secrets or API keys
- MCP servers: `mcp_servers.json`
- RAG providers: `rag_providers.json`
- Workflow templates: `app/core/langgraph/workflow/templates/*.yaml`
- Summarization: `SUMMARIZATION_MODEL`, `SUMMARIZATION_BASE_URL`, `SUMMARIZATION_TRIGGER_TOKENS`, `SUMMARIZATION_KEEP_MESSAGES`
- Long-term memory LLM: `LONG_TERM_MEMORY_MODEL`, `LONG_TERM_MEMORY_LLM_BASE_URL` (independent from `OPENAI_API_BASE`)
- Embedder: `LONG_TERM_MEMORY_EMBEDDER_MODEL`, `LONG_TERM_MEMORY_EMBEDDER_BASE_URL`, `LONG_TERM_MEMORY_EMBEDDER_DIMS`

## Key Dependencies

- **FastAPI** - Web framework
- **LangGraph** - Agent workflow orchestration
- **LangChain** - LLM abstraction and tools
- **Langfuse** - LLM observability and tracing
- **Pydantic v2** - Data validation and settings
- **structlog** - Structured logging
- **mem0ai** - Long-term memory management
- **PostgreSQL + pgvector** - Database and vector storage
- **SQLModel** - ORM for database models
- **tenacity** - Retry logic
- **rich** - Terminal formatting
- **slowapi** - Rate limiting
- **prometheus-client** - Metrics collection
- **langchain-mcp-adapters** - MCP protocol integration
- **pyyaml** - Workflow template parsing
- **qdrant-client** - Qdrant vector database client
- **httpx** - Async HTTP client for external RAG APIs
- **langchain-postgres** - pgvector LangChain integration
- **asyncpg** - Async PostgreSQL driver
- **pypdf** - PDF document parsing
- **python-docx** - DOCX document parsing
- **langchain-text-splitters** - Text chunking for RAG ingestion
- **React 18** - Frontend UI framework
- **TailwindCSS** - Frontend styling
- **Lucide React** - Frontend icons

## 10 Commandments for This Project

1. All routes must have rate limiting decorators
2. All LLM operations must have Langfuse tracing
3. All async operations must have proper error handling
4. All logs must follow structured logging format with lowercase_underscore event names
5. All retries must use tenacity library
6. All console outputs should use rich formatting
7. All caching should only store successful responses
8. All imports must be at the top of files
9. All database operations must be async
10. All endpoints must have proper type hints and Pydantic models

## Common Pitfalls to Avoid

- ❌ Using f-strings in structlog events
- ❌ Adding imports inside functions
- ❌ Forgetting rate limiting decorators on routes
- ❌ Missing Langfuse tracing on LLM calls
- ❌ Caching error responses
- ❌ Using `logger.error()` instead of `logger.exception()` for exceptions
- ❌ Blocking I/O operations without async
- ❌ Hardcoding secrets or API keys
- ❌ Missing type hints on function signatures
- ❌ Forgetting to add i18n keys to both `zh.json` and `en.json`
- ❌ Using hardcoded API paths instead of `buildChatUrl()` in frontend
- ❌ Creating skills without YAML frontmatter
- ❌ Defining only sync `wrap_tool_call`/`wrap_model_call` without async `awrap_*` counterpart in `AgentMiddleware` subclasses
- ❌ Using sync `agent.get_state()` instead of `await agent.aget_state()` with `AsyncPostgresSaver`

## When Making Changes

Before modifying code:
1. Read the existing implementation first
2. Check for related patterns in the codebase
3. Ensure consistency with existing code style
4. Add appropriate logging with structured format
5. Include error handling with early returns
6. Add type hints and Pydantic models
7. Verify Langfuse tracing is enabled for LLM calls
8. Update i18n files if adding frontend text
9. Register new tools in `app/core/langgraph/tools/__init__.py`
10. Add new API routes to `app/api/v1/api.py`

## References

- LangGraph Documentation: https://langchain-ai.github.io/langgraph/
- LangChain Documentation: https://python.langchain.com/docs/
- FastAPI Documentation: https://fastapi.tiangolo.com/
- Langfuse Documentation: https://langfuse.com/docs
- MCP Specification: https://modelcontextprotocol.io/
- Project Docs: `docs/NEW_FEATURES_GUIDE.md`, `docs/PROJECT_DOCUMENTATION_CN.md`