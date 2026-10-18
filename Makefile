.PHONY: backend-dev frontend-dev

backend-dev:
	cd backend && uv run uvicorn api.main:app --reload --reload-include "*.md"

frontend-dev:
	cd frontend && yarn dev