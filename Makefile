# 统一入口 (Windows 下也可直接用 .venv\Scripts\python.exe tests\run_tests.py)
PY ?= .venv/Scripts/python.exe

.PHONY: test gui snapshot hdr clean

test:
	$(PY) tests/run_tests.py

gui:
	$(PY) src/vc71_gui.py

snapshot:
	$(PY) src/vc71_snapshot.py

hdr:
	$(PY) src/vc71_hdr.py

clean:
	rm -rf output/*.png output/*.hdr output/*.tiff
