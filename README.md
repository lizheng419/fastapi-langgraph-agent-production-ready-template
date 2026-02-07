# FastAPI LangGraph Agent Template

A production-ready FastAPI template for building AI agent applications with LangGraph integration. Features multiple agent architectures (Single, Multi-Agent, Workflow), progressive skill loading with LLM-driven auto-creation, MCP tool integration, human-in-the-loop approvals, and a React frontend with agent mode switching.

## 🌟 Features

- **Multi-Architecture Agent System**

  - **Single Agent** — `create_agent` + composable Middleware stack
  - **Multi-Agent** — Supervisor + Worker pattern with automatic routing
  - **Workflow Engine** — Orchestrator-Worker + LangGraph Send API for multi-step workflows
  - Frontend **Agent Mode Selector** for switching between all 3 modes in real-time

- **Skills & SkillCreator**

  - Progressive disclosure — lightweight descriptions in system prompt, full content loaded on-demand
  - **SkillCreator** — LLM-driven auto-creation and incremental learning of skills
  - Agent tools: `create_skill`, `update_skill`, `list_all_skills`, `load_skill`
  - File persistence in `prompts/_auto/` with version tracking

- **MCP (Model Context Protocol) Integration**

  - SSE and stdio transport support
  - JSON configuration (`mcp_servers.json`)
  - Auto-discovery and tool registration at startup

- **RAG Knowledge Base Integration**

  - Pluggable provider architecture with `BaseRetriever` interface
  - Built-in providers: Qdrant, pgvector, RAGFlow, Generic HTTP (Dify/FastGPT/custom)
  - JSON configuration (`rag_providers.json`) — no code changes needed to add new sources
  - Agent tool `retrieve_knowledge` searches all enabled providers

- **Human-in-the-Loop (HITL) Approvals**

  - Sensitive operation detection with configurable patterns
  - Async approval queue with approve/reject/expire lifecycle
  - Dedicated REST API and frontend approval page

- **Production-Ready Infrastructure**

  - FastAPI with uvloop for high-performance async API
  - PostgreSQL + pgvector for data persistence and vector storage
  - Qdrant vector database for RAG knowledge retrieval
  - LangGraph checkpointing with AsyncPostgresSaver
  - Langfuse for LLM observability and tracing
  - Prometheus metrics + Grafana dashboards
  - Structured logging with structlog
  - Rate limiting per endpoint
  - Docker and Docker Compose support

- **AI & LLM Features**

  - Long-term memory with mem0ai and pgvector
  - LLM Service with tenacity retry + model fallback
  - Multiple model support (GPT-4o, GPT-4o-mini, GPT-5, GPT-5-mini, GPT-5-nano)
  - Streaming responses (SSE) for all agent modes
  - Tool calling and function execution

- **Security**

  - JWT-based authentication with session management
  - CORS configuration and input sanitization
  - Rate limiting protection
  - Non-root Docker user

- **Frontend (React + TailwindCSS)**

  - Agent mode selector (Single / Multi / Workflow)
  - Workflow template picker
  - SSE streaming chat with markdown rendering
  - HITL approval management page
  - i18n support (Chinese / English)

- **Developer Experience**

  - Environment configuration via `.env`
  - Makefile commands for dev, build, test, Docker
  - Model evaluation framework with Langfuse integration
  - Type hints throughout with Pydantic v2 models

## 🚀 Quick Start

### Prerequisites

- Python 3.13+
- PostgreSQL ([see Database setup](#database-setup))
- Docker and Docker Compose (optional)

### Environment Setup

1. Clone the repository:

```bash
git clone <repository-url>
cd <project-directory>
```

2. Create and activate a virtual environment:

```bash
uv sync
```

3. Copy the example environment file:

```bash
cp .env.example .env
```

4. Update `.env` with your configuration (see `.env.example` for reference)

### Database setup

1. Create a PostgreSQL database (e.g Supabase or local PostgreSQL)
2. Update the database connection settings in your `.env` file:

```bash
POSTGRES_HOST=db
POSTGRES_PORT=5432
POSTGRES_DB=cool_db
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
```

- You don't have to create the tables manually, the ORM will handle that for you.But if you faced any issues,please run the `schemas.sql` file to create the tables manually.

### Running the Application

#### Local Development

1. Install dependencies:

```bash
uv sync
```

2. Run the application:

```bash
make [dev|staging|prod] # e.g. make dev
```

1. Go to Swagger UI:

```bash
http://localhost:8000/docs
```

#### Using Docker

The Docker setup uses a three-layer Compose architecture:

| File | Services | Use case |
|------|----------|----------|
| `docker-compose-base.yml` | PostgreSQL + Qdrant | Local dev (infra only) |
| `docker-compose-monitoring.yml` | Prometheus + Grafana + cAdvisor | Observability |
| `docker-compose.yml` | App + Frontend (includes base + monitoring) | Full deployment |

```bash
# Full stack (all services)
docker compose up -d

# Infra only (for local dev — run app natively)
docker compose -f docker-compose-base.yml up -d

# Infra + monitoring (no app)
docker compose -f docker-compose-base.yml -f docker-compose-monitoring.yml up -d
```

Access the services:

- **API**: http://localhost:8000 / Swagger: http://localhost:8000/docs
- **Frontend**: http://localhost:3001
- **Prometheus**: http://localhost:9090
- **Grafana**: http://localhost:3000 (admin / admin)
- **Qdrant**: http://localhost:6333

## 📊 Model Evaluation

The project includes a robust evaluation framework for measuring and tracking model performance over time. The evaluator automatically fetches traces from Langfuse, applies evaluation metrics, and generates detailed reports.

### Running Evaluations

You can run evaluations with different options using the provided Makefile commands:

```bash
# Interactive mode with step-by-step prompts
make eval [ENV=development|staging|production]

# Quick mode with default settings (no prompts)
make eval-quick [ENV=development|staging|production]

# Evaluation without report generation
make eval-no-report [ENV=development|staging|production]
```

### Evaluation Features

- **Interactive CLI**: User-friendly interface with colored output and progress bars
- **Flexible Configuration**: Set default values or customize at runtime
- **Detailed Reports**: JSON reports with comprehensive metrics including:
  - Overall success rate
  - Metric-specific performance
  - Duration and timing information
  - Trace-level success/failure details

### Customizing Metrics

Evaluation metrics are defined in `evals/metrics/prompts/` as markdown files:

1. Create a new markdown file (e.g., `my_metric.md`) in the prompts directory
2. Define the evaluation criteria and scoring logic
3. The evaluator will automatically discover and apply your new metric

### Viewing Reports

Reports are automatically generated in the `evals/reports/` directory with timestamps in the filename:

```
evals/reports/evaluation_report_YYYYMMDD_HHMMSS.json
```

Each report includes:

- High-level statistics (total trace count, success rate, etc.)
- Per-metric performance metrics
- Detailed trace-level information for debugging

## 🔧 Configuration

The application uses a flexible configuration system with environment-specific settings:

- `.env` — All environment settings (copy from `.env.example`)
- `.env.example` — Template with placeholder values (committed to git)

### Environment Variables

Key configuration variables include:

```bash
# Application
APP_ENV=development
PROJECT_NAME="FastAPI LangGraph Agent"
DEBUG=true

# Database
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=mydb
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres

# LLM Configuration
OPENAI_API_KEY=your_openai_api_key
DEFAULT_LLM_MODEL=gpt-4o
DEFAULT_LLM_TEMPERATURE=0.7
MAX_TOKENS=4096

# Long-Term Memory
LONG_TERM_MEMORY_COLLECTION_NAME=agent_memories
LONG_TERM_MEMORY_MODEL=gpt-4o-mini
LONG_TERM_MEMORY_EMBEDDER_MODEL=text-embedding-3-small

# Observability
LANGFUSE_PUBLIC_KEY=your_public_key
LANGFUSE_SECRET_KEY=your_secret_key
LANGFUSE_HOST=https://cloud.langfuse.com

# Security
SECRET_KEY=your_secret_key_here
ACCESS_TOKEN_EXPIRE_MINUTES=30

# Rate Limiting
RATE_LIMIT_ENABLED=true
```

## 🧠 Long-Term Memory

The application includes a sophisticated long-term memory system powered by mem0ai and pgvector:

### Features

- **Semantic Memory Storage**: Stores and retrieves memories based on semantic similarity
- **User-Specific Memories**: Each user has their own isolated memory space
- **Automatic Memory Management**: Memories are automatically extracted, stored, and retrieved
- **Vector Search**: Uses pgvector for efficient similarity search
- **Configurable Models**: Separate models for memory processing and embeddings

### How It Works

1. **Memory Addition**: During conversations, important information is automatically extracted and stored
2. **Memory Retrieval**: Relevant memories are retrieved based on conversation context
3. **Memory Search**: Semantic search finds related memories across conversations
4. **Memory Updates**: Existing memories can be updated as new information becomes available

## 🤖 LLM Service

The LLM service provides robust, production-ready language model interactions with automatic retry logic and multiple model support.

### Features

- **Multiple Model Support**: Pre-configured support for GPT-4o, GPT-4o-mini, GPT-5, and GPT-5 variants
- **Automatic Retries**: Uses tenacity for exponential backoff retry logic
- **Reasoning Configuration**: GPT-5 models support configurable reasoning effort levels
- **Environment-Specific Tuning**: Different parameters for development vs production
- **Fallback Mechanisms**: Graceful degradation when primary models fail

### Supported Models

| Model       | Use Case                | Reasoning Effort |
| ----------- | ----------------------- | ---------------- |
| gpt-5       | Complex reasoning tasks | Medium           |
| gpt-5-mini  | Balanced performance    | Low              |
| gpt-5-nano  | Fast responses          | Minimal          |
| gpt-4o      | Production workloads    | N/A              |
| gpt-4o-mini | Cost-effective tasks    | N/A              |

### Retry Configuration

- Automatically retries on API timeouts, rate limits, and temporary errors
- **Max Attempts**: 3
- **Wait Strategy**: Exponential backoff (1s, 2s, 4s)
- **Logging**: All retry attempts are logged with context

## 📝 Advanced Logging

The application uses structlog for structured, contextual logging with automatic request tracking.

### Features

- **Structured Logging**: All logs are structured with consistent fields
- **Request Context**: Automatic binding of request_id, session_id, and user_id
- **Environment-Specific Formatting**: JSON in production, colored console in development
- **Performance Tracking**: Automatic logging of request duration and status
- **Exception Tracking**: Full stack traces with context preservation

### Logging Context Middleware

Every request automatically gets:
- Unique request ID
- Session ID (if authenticated)
- User ID (if authenticated)
- Request path and method
- Response status and duration

### Log Format Standards

- **Event Names**: lowercase_with_underscores
- **No F-Strings**: Pass variables as kwargs for proper filtering
- **Context Binding**: Always include relevant IDs and context
- **Appropriate Levels**: debug, info, warning, error, exception

## ⚡ Performance Optimizations

### uvloop Integration

The application uses uvloop for enhanced async performance (automatically enabled via Makefile):

**Performance Improvements**:
- 2-4x faster asyncio operations
- Lower latency for I/O-bound tasks
- Better connection pool management
- Reduced CPU usage for concurrent requests

### Connection Pooling

- **Database**: Async connection pooling with configurable pool size
- **LangGraph Checkpointing**: Shared connection pool for state persistence
- **Redis** (optional): Connection pool for caching

### Caching Strategy

- Only successful responses are cached
- Configurable TTL based on data volatility
- Cache invalidation on updates
- Supports Redis or in-memory caching

## 🔌 API Reference

### Authentication

- `POST /api/v1/auth/register` - Register a new user
- `POST /api/v1/auth/login` - Authenticate and receive JWT token
- `POST /api/v1/auth/session` - Create a new chat session
- `GET /api/v1/auth/sessions` - List user sessions
- `POST /api/v1/auth/logout` - Logout and invalidate session

### Chat (create_agent + Middleware)

- `POST /api/v1/chatbot/chat?mode=single|multi` - Chat response
- `POST /api/v1/chatbot/chat/stream?mode=single|multi` - Streaming response (SSE)
- `GET /api/v1/chatbot/messages` - Get conversation history
- `DELETE /api/v1/chatbot/messages` - Clear chat history

### Workflow Chat (Orchestrator-Worker)

- `POST /api/v1/chatbot/workflow/chat[?template=name]` - Execute workflow
- `POST /api/v1/chatbot/workflow/chat/stream[?template=name]` - Streaming workflow (SSE)
- `GET /api/v1/chatbot/workflow/templates` - List available workflow templates

### HITL Approvals

- `GET /api/v1/approvals/pending` - List pending approval requests
- `GET /api/v1/approvals/{id}` - Get approval request detail
- `POST /api/v1/approvals/{id}/approve` - Approve a request
- `POST /api/v1/approvals/{id}/reject` - Reject a request

### Health & Monitoring

- `GET /api/v1/health` - Health check
- `GET /metrics` - Prometheus metrics endpoint

For detailed API documentation, visit `/docs` (Swagger UI) or `/redoc` (ReDoc) when running the application.

## 📚 Project Structure

```text
fastapi-langgraph-agent/
├── app/
│   ├── api/v1/
│   │   ├── api.py                    # API router aggregation
│   │   ├── auth.py                   # Authentication endpoints
│   │   ├── chatbot_v1.py             # Chat endpoints (Single + Multi Agent)
│   │   ├── chatbot_workflow.py       # Workflow chat endpoints
│   │   ├── sse.py                    # Shared SSE event generator
│   │   └── approval.py               # HITL approval endpoints
│   ├── core/
│   │   ├── config.py                 # Configuration management
│   │   ├── logging.py                # Structured logging (structlog)
│   │   ├── metrics.py                # Prometheus metrics
│   │   ├── middleware.py             # Request context middleware
│   │   ├── limiter.py                # Rate limiting (slowapi)
│   │   ├── langgraph/
│   │   │   ├── base.py              # BaseAgentMixin (shared infrastructure)
│   │   │   ├── tools/                # Agent tools (search, skills, etc.)
│   │   │   ├── agents/               # Worker definitions & registry
│   │   │   ├── hitl/                 # Human-in-the-Loop approval system
│   │   │   ├── v1/
│   │   │   │   ├── agent.py          # V1Agent (create_agent + Middleware)
│   │   │   │   ├── multi_agent.py    # V1MultiAgent (Supervisor + Workers)
│   │   │   │   └── middleware.py     # 5 composable Middleware classes
│   │   │   └── workflow/
│   │   │       ├── graph.py          # WorkflowGraph (Orchestrator-Worker)
│   │   │       ├── planner.py        # WorkflowPlanner (YAML + LLM)
│   │   │       ├── templates.py      # Template registry
│   │   │       └── templates/*.yaml  # Workflow YAML templates
│   │   ├── rag/                       # RAG knowledge base integration
│   │   │   ├── base.py               # BaseRetriever abstract interface
│   │   │   ├── manager.py            # RetrieverManager (registry + routing)
│   │   │   ├── schema.py             # RAGDocument, RetrievalQuery, RetrievalResult
│   │   │   └── providers/            # Qdrant, pgvector, RAGFlow, GenericHTTP
│   │   ├── mcp/                      # MCP (Model Context Protocol) integration
│   │   ├── skills/
│   │   │   ├── schema.py             # Skill Pydantic model
│   │   │   ├── registry.py           # SkillRegistry + agent tools
│   │   │   ├── creator.py            # SkillCreator (LLM auto-creation)
│   │   │   └── prompts/              # Skill markdown files
│   │   │       └── _auto/            # Auto-generated skills
│   │   └── prompts/
│   │       ├── __init__.py           # Prompt loader with Skills injection
│   │       └── system.md             # System prompt template
│   ├── models/                       # SQLModel ORM models
│   ├── schemas/                      # Pydantic request/response schemas
│   ├── services/
│   │   ├── database.py               # Async database service
│   │   └── llm.py                    # LLM service with retry + fallback
│   ├── utils/                        # Graph and general utilities
│   └── main.py                       # FastAPI application entry point
├── frontend/
│   ├── src/
│   │   ├── api.js                    # Backend API client (multi-mode)
│   │   ├── App.jsx                   # React router + auth state
│   │   ├── pages/
│   │   │   ├── ChatPage.jsx          # Chat UI + Agent mode selector
│   │   │   ├── LoginPage.jsx         # Login/register page
│   │   │   └── ApprovalsPage.jsx     # HITL approval management
│   │   └── i18n/                     # Internationalization (zh/en)
│   ├── package.json
│   └── vite.config.js
├── tests/                            # Test suite
├── evals/                            # Model evaluation framework
├── docs/                             # Detailed documentation
├── grafana/                          # Grafana dashboard provisioning
├── prometheus/                       # Prometheus scrape configuration
├── scripts/                          # Docker & deployment scripts
├── docker-compose.yml                # Full stack (includes base + monitoring)
├── docker-compose-base.yml           # Infrastructure (PostgreSQL + Qdrant)
├── docker-compose-monitoring.yml      # Monitoring (Prometheus + Grafana + cAdvisor)
├── Dockerfile                        # Backend Docker image (multi-stage build)
├── Makefile                          # Development commands
├── pyproject.toml                    # Python dependencies (uv)
├── rag_providers.json                # RAG knowledge base provider configuration
├── schema.sql                        # PostgreSQL schema
├── mcp_servers.json                  # MCP server configuration
├── AGENTS.md                         # AI agent development guide
├── SECURITY.md                       # Security policy
└── README.md                         # This file
```

## 🛡️ Security

For security concerns, please review our [Security Policy](SECURITY.md).

## 📄 License

This project is licensed under the terms specified in the [LICENSE](LICENSE) file.

## 🤝 Contributing

Contributions are welcome! Please ensure:

1. Code follows the project's coding standards
2. All tests pass
3. New features include appropriate tests
4. Documentation is updated
5. Commit messages follow conventional commits format

## 📞 Support

For issues, questions, or contributions, please open an issue on the project repository
