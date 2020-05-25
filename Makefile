all:
	@echo "only 'make check' for now"

SHELLTEST_OPTIONS :=

SHELL_TESTS := \
	basic.sh \
	check.sh \
	reuse.sh

TEST_PYTHONS   := python2 python3
TEST_DATABASES := sqlite postgresql

.PHONY: shelltests
shelltests:
	@cd shelltests ; \
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
	    PYTHON=$$python ./unittests.sh || status=false ; \
	done ;\
	$$status

check:
	@$(MAKE) unittests
	@$(MAKE) shelltests
