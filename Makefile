PYTHON ?= python3

.PHONY: run run2d install check clean help

help:
	@echo "make install  — установить зависимости (ursina, pygame, numpy, pillow)"
	@echo "make run      — запустить 3D-версию игры"
	@echo "make run2d    — запустить старую 2D-версию (вид сверху)"
	@echo "make check    — проверить, что все модули компилируются"
	@echo "make clean    — удалить кэш, сгенерированные звуки и сохранение"

install:
	$(PYTHON) -m pip install -r requirements.txt

run:
	$(PYTHON) main.py

run2d:
	$(PYTHON) main2d.py

check:
	$(PYTHON) -m py_compile *.py && echo "OK"

clean:
	rm -rf __pycache__ sounds savegame.json
