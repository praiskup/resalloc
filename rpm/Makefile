PYTHON = python3

project = resalloc

tarball_version = \
	cd .. ; \
	$(PYTHON) setup.py --version

project_version = ./spec-version

generate_tarball = \
	cd .. ; \
	$(PYTHON) setup.py sdist --dist-dir rpm

git_rev = \
	rev="$$(git rev-parse HEAD)" ; \
	rev_short=$${rev:0:5} ; \
	echo $$rev_short

rpmbuild_options = \
	--define "_sourcedir $(PWD)" \
	--define "_rpmdir $(PWD)" \
	--define "_specdir $(PWD)" \
	--define "_builddir $(PWD)" \
	--define "_srcrpmdir $(PWD)" \
	--define "dist %nil"

tarball = "$(project)-$(shell $(project_version)).tar.gz"

spec = $(project).spec

all: srpm

.PHONY: $(spec)
$(spec):
	version=$(shell $(project_version)) ; \
	tbversion=$(shell $(tarball_version)) ; \
	replace=%version ; \
	if test "$$version" != "$$tbversion" ; then \
	    replace=$$tbversion ; \
	fi; \
	rm -f $(spec); \
	sed -e "s/@VERSION@/$$version/" \
	    -e "s/@TARBALL_VERSION@/$$replace/" \
	    $(spec).tpl > $(spec) ; \
	chmod -w $(spec)

$(tarball): clean
	$(generate_tarball)

srpm: $(tarball) $(spec)
	rm -rf *.src.rpm
	rpmbuild -bs --define _disable_source_fetch\ 0 $(rpmbuild_options) $(spec)

rpm: srpm
	rpmbuild --rebuild *.src.rpm --define "_rpmdir $(PWD)"


clean:
	rm -rf *.src.rpm *.tar.gz $(project)-*/
