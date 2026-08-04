# Intentionally empty.
#
# pytest inserts the directory containing the rootmost conftest.py into sys.path, which is
# what lets `tests/*.py` do `import watch` / `import scraper` etc. Without this file, only
# `python -m pytest` works (that form adds the CWD to sys.path itself) and the bare
# `pytest` command fails with ModuleNotFoundError for every module under test.
