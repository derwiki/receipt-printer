VENV_DIR := .venv
LOCKFILE := uv.lock
REQUIREMENTS := requirements.in
UVICORN_CMD := uvicorn main:app --host 0.0.0.0 --port 8000

install:
	uv venv $(VENV_DIR)
	source $(VENV_DIR)/bin/activate && uv pip sync $(LOCKFILE)

lock:
	uv pip compile $(REQUIREMENTS) > $(LOCKFILE)

freeze:
	source $(VENV_DIR)/bin/activate && uv pip freeze > $(REQUIREMENTS)

clean:
	rm -rf $(VENV_DIR)

run:
	source $(VENV_DIR)/bin/activate && $(UVICORN_CMD)

run-dummy:
	source $(VENV_DIR)/bin/activate && USE_PRINTER_DUMMY=true $(UVICORN_CMD)

run-real:
	source $(VENV_DIR)/bin/activate && USE_PRINTER_DUMMY=false $(UVICORN_CMD)

test:
	source .venv/bin/activate && pytest test_main.py
