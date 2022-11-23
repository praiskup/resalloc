%global srcname resalloc

%global sysuser  resalloc
%global sysgroup %sysuser
%global _logdir  %_var/log/%{name}server
%global _homedir %_sharedstatedir/%{name}server

%global sum Resource allocator for expensive resources
%global desc \
The resalloc project aims to help with taking care of dynamically \
allocated resources, for example ephemeral virtual machines used for \
the purposes of CI/CD tasks.


%bcond_without check

%if 0%{?fedora} || 0%{?rhel} > 7 || 0%{?is_opensuse}
%bcond_with    python2
%bcond_without python3
%else
%bcond_without python2
%bcond_with    python3
%endif

%global default_python  %{?with_python3:python3}%{!?with_python3:python2}
%global default_sitelib %{?with_python3:%python3_sitelib}%{!?with_python3:%python_sitelib}

Name:       %srcname
Summary:    %sum - client tooling
Version:    @VERSION@
Release:    1%{?dist}
License:    GPLv2+
URL:        https://github.com/praiskup/resalloc
BuildArch:  noarch

BuildRequires: make
BuildRequires: postgresql-server


%if %{with python3}
BuildRequires: python3-alembic
BuildRequires: python3-argparse-manpage
BuildRequires: python3-devel
BuildRequires: python3-psycopg2
BuildRequires: python3-pytest
BuildRequires: python3-pytest-cov
BuildRequires: python3-setuptools
BuildRequires: python3-six
BuildRequires: python3-sqlalchemy
%if 0%{?is_opensuse}
BuildRequires: python3-PyYAML
BuildRequires: cron
%else
BuildRequires: python3-yaml
%endif
%endif

%if %{with python2}
BuildRequires: python-alembic
BuildRequires: python2-argparse-manpage
BuildRequires: python2-devel
BuildRequires: python-psycopg2
BuildRequires: python2-mock
BuildRequires: python2-pytest
BuildRequires: python2-pytest-cov
BuildRequires: python2-setuptools
BuildRequires: python2-six
BuildRequires: python-sqlalchemy
BuildRequires: python-yaml
%endif

Requires:   %default_python-%srcname = %version-%release

Source0: https://github.com/praiskup/%name/releases/download/v%version/%name-@TARBALL_VERSION@.tar.gz
Source1: resalloc.service
Source2: logrotate
Source3: merge-hook-logs
Source4: cron.hourly

%description
%desc

The %name package provides the client-side tooling.


%package server
Summary:    %sum - server part

Requires: crontabs
Requires: logrotate
Requires:   %default_python-%srcname = %version-%release
%if %{with python3}
Requires: python3-alembic
Requires: python3-six
Requires: python3-sqlalchemy
Requires: python3-yaml
%else
Requires: python-alembic
Requires: python2-six
Requires: python-sqlalchemy
Requires: python-yaml
%endif

Requires(pre): /usr/sbin/useradd
%description server
%desc

The %name-server package provides the resalloc server, and
some tooling for resalloc administrators.

%if %{with python3}
%package webui
Summary:    %sum - webui part

%if %{with python3}
Requires:   %default_python-%srcname = %version-%release
Requires: %name-server
Requires: python3-flask
Recommends: %name-selinux
%endif

%description webui
%desc

The %name-webui package provides the resalloc webui,
it shows page with information about resalloc resources.
%endif

%if %{with python3}
%package -n python3-%srcname
Summary: %sum - Python 3 client library
%{?python_provide:%python_provide python3-%srcname}
%description -n python3-%srcname
%desc

The python3-%name package provides Python 3 client library for talking
to the resalloc server.
%endif


%if %{with python2}
%package -n python2-%srcname
Summary: %sum - Python 2 client library
%{?python_provide:%python_provide python2-%srcname}
%description -n python2-%srcname
%desc

The python2-%name package provides Python 2 client library for talking
to the resalloc server.
%endif


%package selinux
Summary: SELinux module for %{name}
Requires: %name-webui = %version-%release
# Requires(post): policycoreutils-python
BuildRequires: selinux-policy-devel
%{?selinux_requires}

%description selinux
%desc

%post selinux
semanage fcontext -a -t httpd_sys_script_exec_t \
    %_var/www/cgi-%{name} 2>/dev/null || :
restorecon -R %_var/www/cgi-%{name} || :


%prep
%autosetup -p1 -n %name-@TARBALL_VERSION@


%build
%if %{with python2}
%py2_build
%else
%py3_build
%endif


%install
%if %{with python2}
%py2_install
rm -r %buildroot%python2_sitelib/%{name}webui
%else
%py3_install
install -d -m 755 %buildroot%_datadir/%{name}webui
cp -r %{name}webui/templates %buildroot%_datadir/%{name}webui/
cp -r %{name}webui/static %buildroot%_datadir/%{name}webui/

install -d -m 755 %buildroot%_var/www/
install -p -m 755 %{name}webui/cgi-resalloc %buildroot%_var/www/cgi-%{name}
%endif

mkdir -p %buildroot%_unitdir
mkdir -p %buildroot%_logdir
install -p -m 644 %SOURCE1 %buildroot%_unitdir
install -d -m 700 %buildroot%_homedir
install -d -m 700 %buildroot%_sysconfdir/logrotate.d
install -p -m 644 %SOURCE2 %buildroot%_sysconfdir/logrotate.d/resalloc-server
install -p -m 644 man/resalloc-server.1 %buildroot%_mandir/man1
install -d -m 755 %buildroot/%_libexecdir
install -p -m 755 %SOURCE3 %buildroot/%_libexecdir/%name-merge-hook-logs
install -d %buildroot%_sysconfdir/cron.hourly
install -p -m 755 %SOURCE4 %buildroot%_sysconfdir/cron.hourly/resalloc


%if %{with check}
%check
%if %{with python2}
make check TEST_PYTHONS="python2"
%else
make check TEST_PYTHONS="python3"
%endif
%endif


# Simplify "alembic upgrade head" actions.
ln -s "%{default_sitelib}/%{name}server" %buildroot%_homedir/project


%pre server
user=%sysuser
group=%sysgroup
getent group "$user" >/dev/null || groupadd -r "$group"
getent passwd "$user" >/dev/null || \
useradd -r -g "$group" -G "$group" -s /bin/bash \
        -c "resalloc server's user" "$user" \
        -d "%_homedir"


%post server
%systemd_post resalloc.service

%postun server
%systemd_postun_with_restart resalloc.service


%global doc_files NEWS README

%files
%doc %doc_files
%license COPYING
%{_bindir}/%{name}
%_mandir/man1/%{name}.1*


%if %{with python3}
%files -n python3-%srcname
%doc %doc_files
%license COPYING
%{python3_sitelib}/%{name}
%{python3_sitelib}/%{name}-*.egg-info
%endif


%if %{with python2}
%files -n python2-%srcname
%doc %doc_files
%license COPYING
%{python2_sitelib}/%{name}
%{python2_sitelib}/%{name}-*.egg-info
%endif


%files server
%doc %doc_files
%license COPYING
%{default_sitelib}/%{name}server
%{_bindir}/%{name}-server
%{_bindir}/%{name}-maint
%{_bindir}/%{name}-check-vm-ip
%attr(0750, %sysuser, %sysgroup) %dir %{_sysconfdir}/%{name}server
%config(noreplace) %{_sysconfdir}/%{name}server/*
%_unitdir/resalloc.service
%attr(0700, %sysuser, %sysgroup) %dir %_logdir
%_mandir/man1/%{name}-maint.1*
%_mandir/man1/%{name}-server.1*
%attr(0700, %sysuser, %sysgroup) %_homedir
%config %_sysconfdir/logrotate.d/resalloc-server
%_libexecdir/resalloc-merge-hook-logs
%config %attr(0755, root, root) %{_sysconfdir}/cron.hourly/resalloc

%if %{with python3}
%files webui
%doc %doc_files
%license COPYING
%{default_sitelib}/%{name}webui/
%_datadir/%{name}webui/
%_var/www/cgi-%{name}
%endif

%files selinux


%changelog
* Fri Aug 02 2019 Pavel Raiskup <praiskup@redhat.com> - 2.6-1
- don't assign resources to closed tickets

* Thu Jun 13 2019 Pavel Raiskup <praiskup@redhat.com> - 2.5-1
- thread safety - don't change os.environ

* Tue Jun 11 2019 Pavel Raiskup <praiskup@redhat.com> - 2.4-1
- fix improperly handled thread communication

* Fri May 10 2019 Pavel Raiskup <praiskup@redhat.com> - 2.3-3
- drop mkhomedir requires leftover
- configure logrotate to compress rotated logs

* Fri May 10 2019 Pavel Raiskup <praiskup@redhat.com> - 2.3-2
- fix logrotate typo s/lib/log/, package it as config file

* Fri May 10 2019 Pavel Raiskup <praiskup@redhat.com> - 2.3-1
- logrotate config (per review rhbz#1707302)
- provide manual page for resalloc-server (per rhbz#1707302)
- logrotate also the hooks directory

* Fri May 10 2019 Pavel Raiskup <praiskup@redhat.com> - 2.2-2
- move homedir from /home to /var/lib (per msuchy's review)

* Thu May 09 2019 Pavel Raiskup <praiskup@redhat.com> - 2.2-1
- new release

* Tue May 07 2019 Pavel Raiskup <praiskup@redhat.com> - 2.1-3
- provide summary/description (per msuchy's review)

* Tue May 07 2019 Pavel Raiskup <praiskup@redhat.com> - 2.1-2
- only support Python 3 or Python 2

* Tue May 07 2019 Pavel Raiskup <praiskup@redhat.com> - 2.1-1
- fixed racy testsuite

* Tue May 07 2019 Pavel Raiskup <praiskup@redhat.com> - 2.0-1
- release 2.0 (changed db schema for "id" within pool)

* Wed Oct 31 2018 Pavel Raiskup <praiskup@redhat.com> - 1.1-1
- bump, rebuild for Python 3.7

* Tue Jan 30 2018 Pavel Raiskup <praiskup@redhat.com> - 1.1-0
- release with removed 'cat' hack (commit 970b99725acf1dc)

* Thu Jan 18 2018 Pavel Raiskup <praiskup@redhat.com> - 0.1-12
- first release

* Wed Jan 17 2018 Pavel Raiskup <praiskup@redhat.com> - 0.dev0-12
- better setup default directories

* Wed Jan 17 2018 Pavel Raiskup <praiskup@redhat.com> - 0.dev0-11
- log both stdout and stderr for start/stop/livecheck commands

* Sat Jan 06 2018 Pavel Raiskup <praiskup@redhat.com> - 0.dev0-10
- service: add WantedBy=multi-user.target

* Fri Sep 29 2017 Pavel Raiskup <praiskup@redhat.com> - 0.dev0-9
- fix homedir for ansible

* Fri Sep 29 2017 Pavel Raiskup <praiskup@redhat.com> - 0.dev0-8
- resalloc-maint resource-delete fix

* Thu Sep 28 2017 Pavel Raiskup <praiskup@redhat.com> - 0.dev0-7
- resalloc ticket-wait puts output to stdout
- new command resalloc-maint ticket-list

* Tue Sep 26 2017 Pavel Raiskup <praiskup@redhat.com> - 0.dev0-6
- create datadir directory for database files

* Tue Sep 26 2017 Pavel Raiskup <praiskup@redhat.com> - 0.dev0-5
- install manual pages
- add '--with check' option

* Thu Sep 21 2017 Pavel Raiskup <praiskup@redhat.com> - 0.dev0-4
- python2/python3 fixes

* Wed Sep 20 2017 Pavel Raiskup <praiskup@redhat.com> - 0.dev0-3
- resalloc user is not nologin anymore
- add resalloc-maint

* Tue Sep 19 2017 Pavel Raiskup <praiskup@redhat.com> - 0.dev0-2
- add service file
- install log directory for server

* Mon Sep 18 2017 Pavel Raiskup <praiskup@redhat.com>
- no changelog
