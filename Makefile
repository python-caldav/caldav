TOX_DIR = .tox
BIN_DIR = ${TOX_DIR}/py37/bin/

install:
	tox --recreate --notest

test:
	tox

package:
	$(BIN_DIR)pip install wheel
	$(BIN_DIR)python setup.py sdist bdist_wheel


doc:
	$(BIN_DIR)pip install sphinx
	$(BIN_DIR)python setup.py build_sphinx

clean:
	find . -name __pycache__ -exec rm -r {} +
	rm -rf caldav.egg-info dist docs/build ${TOX_DIR}

mrproper: clean
	rm -rf ${TOX_DIR}
