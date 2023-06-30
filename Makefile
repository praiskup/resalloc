all:
	@echo "only 'make check' for now"

SHELLTEST_OPTIONS :=

SHELL_TESTS := \
	basic.sh \
	check.sh \
	ondemand.sh \
	reuse.sh

TEST_PYTHONS   := python3
TEST_DATABASES := sqlite postgresql

.PHONY: shelltests
shelltests:
	cd shelltests ; \
	status=true ; \
	for python in $(TEST_PYTHONS); do \
	    for database in $(TEST_DATABASES); do \
		PYTHON=$$python DATABASE=$$database \
		    ./testrunner $(SHELLTEST_OPTIONS) $(SHELL_TESTS) ; \
		test $$? -eq 0 || status=false ; \
	    done ; \
	done ; \
	$$status

.PHONY: unittests
unittests:
	status=true ; \
	for python in $(TEST_PYTHONS); do \
	    PYTHON=$$python ./unittests.sh -vv || status=false ; \
	done ;\
	$$status

check:
	$(MAKE) unittests
	$(MAKE) shelltests

ERDFILE = erd.png

$(ERDFILE): ./resallocserver/models.py
	export CONFIG_DIR=`pwd`/etc ; \
	export PYTHONPATH=`pwd` ; \
	python3 -c "from resallocserver.models import Base ; from eralchemy import render_er;  \
		render_er(Base, '$@')"
