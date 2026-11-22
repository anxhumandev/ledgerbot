.PHONY: setup data train baseline baseline-sim dev teach test e2e

PYTHON_BOOTSTRAP ?= python3
PYTHON := $(abspath $(if $(wildcard .venv/Scripts/python.exe),.venv/Scripts/python.exe,.venv/bin/python))
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

baseline-sim:
	cd backend && "$(PYTHON)" -m app.eval.baseline_sim

dev:
	"$(PYTHON)" dev.py

teach:
	cd backend && "$(PYTHON)" -m app.pipeline.normalize teach

test:
	cd backend && "$(PYTHON)" -m pytest -q
	cd frontend && npm test && npm run build

e2e:  # needs the app running (make dev)
	cd frontend && npm run test:e2e
