# SimplyCashIN backend (M1)

    python -m venv .venv && . .venv/Scripts/activate   # Windows
    pip install -e ".[dev]"
    docker compose up -d
    createdb / auto: tests create scin_test schema
    cp .env.example .env   # set ANTHROPIC_API_KEY
    uvicorn app.api.app:app --reload

Run tests: `python -m pytest`
