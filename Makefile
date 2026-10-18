.PHONY: backend-dev frontend-dev

backend-dev:
	cd backend && uv run uvicorn api.main:app --reload

frontend-dev:
	cd frontend && yarn dev