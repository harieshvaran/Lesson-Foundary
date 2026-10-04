# LessonFoundry

LessonFoundry is a teacher-facing studio that converts one trusted teaching source plus explicit learning objectives into a connected, aligned learning pack (explanation, worked example, quiz with key, two-level practice, revision sheet).

## Architecture & Technology Stack
- **Backend**: Python 3.11+, FastAPI, SQLAlchemy, SQLite, Pydantic v2
- **Frontend**: React + Vite
- **LLM Layer**: Pluggable provider interface (`LLMProvider`) supporting strict Pydantic validation, provenance tracking, and zero hard-coded content.
- **Testing & Eval**: pytest unit/integration suite, automated prompt injection and gap detection evaluation harness.

## Quick Start

### 1. Backend Setup
```bash
python -m venv .venv
# On Windows:
.venv\Scripts\activate
# On Unix:
source .venv/bin/activate

pip install -r backend/requirements.txt
```

### 2. Environment Configuration
Copy `.env.example` to `.env` and set your credentials:
```bash
cp .env.example .env
```

### 3. Run Backend Server
```bash
uvicorn backend.app.main:app --reload
```

### 4. Run Tests
```bash
pytest tests/
```

## Known Limitations
- Phase 0 foundation build complete. Full pipeline generation and UI under active development.
