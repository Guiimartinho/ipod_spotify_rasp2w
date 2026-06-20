# Convenience targets. The Python test suite is stdlib-only (no install needed).
PYTHON ?= python3

.PHONY: test compile clickwheel clean

test:                ## Run the unit test suite
	cd frontend && $(PYTHON) -m unittest discover -s tests

compile:             ## Byte-compile all frontend modules (syntax check)
	cd frontend && $(PYTHON) -m py_compile \
		config.py serialization.py input_decoder.py \
		datastore.py spotify_manager.py view_model.py spotifypod.py

clickwheel:          ## Build the click-wheel C driver (Raspberry Pi only)
	$(MAKE) -C clickwheel

clean:               ## Remove build artifacts and __pycache__
	-$(MAKE) -C clickwheel clean
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
