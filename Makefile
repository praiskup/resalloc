all:
	@echo "only 'make check' for now"

SHELLTEST_OPTIONS :=

SHELL_TESTS := \
	basic.sh

TEST_PYTHONS   := python2 python3
TEST_DATABASES := sqlite postgresql

.PHONY: shelltests
shelltests:
	@cd shelltests ; \
	status=true ; \
	for python in $(TEST_PYTHONS); do \
	    for database in $(TEST_DATABASES); do \
		echo "=> $$python $$database" ; \
		PYTHON=$$python DATABASE=$$database \
		    ./testrunner $(SHELLTEST_OPTIONS) $(SHELL_TESTS) ; \
		test $$? -eq 0 || status=false ; \
	    done ; \
	done ; \
	$$status

check: shelltests
