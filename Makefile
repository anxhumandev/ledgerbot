.PHONY: setup data train baseline dev reset teach test

PYTHON_BOOTSTRAP ?= python3
PYTHON := $(abspath .venv/bin/python)
PORT_BACK ?= 8100

setup:
	$(PYTHON_BOOTSTRAP) -m venv .venv
	"$(PYTHON)" -m pip install -r backend/requirements.txt
	cd frontend && npm ci

data:
	cd backend && "$(PYTHON)" -m data.generate

train:
	cd backend && "$(PYTHON)" -m app.pipeline.run

baseline:
	cd backend && "$(PYTHON)" -m app.eval.baseline_llm

dev:
	"$(PYTHON)" dev.py

reset:
	curl -fsS -X POST http://localhost:$(PORT_BACK)/api/demo/reset

teach:
	cd backend && "$(PYTHON)" -m app.pipeline.normalize teach

test:
	cd backend && "$(PYTHON)" -m pytest -q
	cd frontend && npm run build
