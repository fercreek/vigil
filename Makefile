PYTHON ?= /Users/fernandocastaneda/Documents/ideas/scalp_bot/venv/bin/python

.PHONY: knowledge-refresh
knowledge-refresh:
	$(PYTHON) -m instrument.knowledge.refresh
