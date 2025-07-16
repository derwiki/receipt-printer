VENV_DIR := .venv
REQUIREMENTS := requirements.in
LOCKFILE := uv.lock

# Install dependencies from uv.lock (reproducible)
install:
	uv venv $(VENV_DIR)
	source $(VENV_DIR)/bin/activate && uv pip sync $(LOCKFILE)

# Compile uv.lock from requirements.in
lock:
	uv pip compile $(REQUIREMENTS) > $(LOCKFILE)

# Create requirements.in from current venv (if needed)
freeze:
	source $(VENV_DIR)/bin/activate && uv pip freeze > requirements.in

# Remove virtual environment
clean:
	rm -rf $(VENV_DIR)
