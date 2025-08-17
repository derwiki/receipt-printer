VENV_DIR := .venv
LOCKFILE := uv.lock
REQUIREMENTS := requirements.in
UVICORN_CMD := uvicorn main:app --host 0.0.0.0 --port 8000 --reload

install:
	uv venv $(VENV_DIR)
	. $(VENV_DIR)/bin/activate && uv pip install -r requirements.in
	. $(VENV_DIR)/bin/activate && uv pip sync $(LOCKFILE)

lock:
	uv pip compile $(REQUIREMENTS) --universal > $(LOCKFILE)

freeze:
	. $(VENV_DIR)/bin/activate && uv pip freeze > $(REQUIREMENTS)

clean:
	rm -rf $(VENV_DIR)

run:
	. $(VENV_DIR)/bin/activate && $(UVICORN_CMD)

run-dummy:
	. $(VENV_DIR)/bin/activate && USE_PRINTER_DUMMY=true $(UVICORN_CMD)

run-real:
	. $(VENV_DIR)/bin/activate && USE_PRINTER_DUMMY=false $(UVICORN_CMD)

test:
	. .venv/bin/activate && pytest test_main.py

format:
	. $(VENV_DIR)/bin/activate && black .

lint:
	. $(VENV_DIR)/bin/activate && ruff check . --fix
