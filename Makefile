all:
	@echo "only 'make check' for now"

SHELLTEST_OPTIONS :=

SHELL_TESTS := \
	basic

.PHONY: shelltests
shelltests:
	@cd shelltests ; \
	./testrunner $(SHELLTEST_OPTIONS) $(SHELL_TESTS)

check: shelltests
