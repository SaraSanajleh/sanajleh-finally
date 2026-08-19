# ReTour AI Brain

ReTour plans personalized Jordan journeys and connects travelers with relevant local tourism businesses. The itinerary is the product tourists see. Helping SMEs grow is the business objective.

## What stays fixed

- Existing tourism datasets: POIs, restaurants, hotels
- Existing SME datasets: tour guides and tour operators
- Wizard request contract (`PackageRequest`)
- GPT-OSS via Ollama (`gpt-oss:20b-cloud`)

## Architecture

```
Wizard Request
      ↓
Input Normalization (TouristProfile)
      ↓
Context Layer  +  RAG Layer  +  SME Layer
      ↓
Central Tourism Planning Agent (GPT-OSS)
      ↓
Schema + business-rule validation
      ↓
Tourism Package → premium UI
```

There is one planner agent. Context, retrieval, and SME intelligence are internal layers.

## Quick start

### Backend

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Start Ollama with GPT-OSS:

```bash
ollama signin
ollama pull gpt-oss:20b-cloud
```

Start the retriever (port 8001), then the Brain (port 8000):

```bash
cd backend\retriever
.\start_retriever.ps1
```

```bash
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

- API docs: http://127.0.0.1:8000/docs
- Health: http://127.0.0.1:8000/api/v1/health

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:3000 — use `/wizard` to generate a package.

### Tests

```bash
pytest tests/ -v
```

## Configuration

LLM settings live in `config/llm.yaml`. Environment overrides are documented in `.env.example`.

Do not commit secrets. API keys and model credentials stay in environment variables.

## Documentation

- [ARCHITECTURE.md](ARCHITECTURE.md)
- [API.md](API.md)
- [DATA.md](DATA.md)
- [RAG.md](RAG.md)
- [SME.md](SME.md)
- [PROMPTS.md](PROMPTS.md)
