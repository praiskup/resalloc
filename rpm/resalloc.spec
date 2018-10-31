%global srcname resalloc

%global sysuser  resalloc
%global sysgroup %sysuser
%global _logdir  %_var/log/%{name}server

%bcond_without check

# Huh, ugly hacks.
%global python2_alembic    python-alembic
%global python2_sqlalchemy python-sqlalchemy
%if 0%{?fedora} >= 26
%global python2_sqlalchemy python2-sqlalchemy
%endif
%if 0%{?fedora} || 0%{?rhel} > 7
%global build_python2 1
%global build_python3 1
%bcond_without python2
%bcond_without python3
%global default_python python3
%global default_python3 true
%global default_sitelib %python3_sitelib
%global default_drop_sitelib %python2_sitelib
%global python2 python2
%else
%global build_python2 1
%bcond_without python2
%bcond_with python3
%global default_python python2
%global default_python2 true
%global default_sitelib %python2_sitelib
%global default_drop_sitelib %python3_sitelib
%global python2 python
%endif

%global server2_both_requires %python2_alembic %python2-six %python2_sqlalchemy %python2-yaml
%global server3_both_requires  python3-alembic  python3-six  python3-sqlalchemy  python3-yaml

%{?default_python2:%global server_both_requires %server2_both_requires}
%{?default_python3:%global server_both_requires %server3_both_requires}


Name:       %srcname
Summary:    Resource allocator - Client
Version:    1.1
Release:    1%{?dist}
License:    GPLv2+
URL:        https://github.com/praiskup/resalloc
BuildArch:  noarch

BuildRequires: postgresql-server


%if %{with python3}
BuildRequires: python3-setuptools
BuildRequires: python3-devel
BuildRequires: %server3_both_requires python3-psycopg2
%endif

%if %{with python2}
BuildRequires: python2-setuptools
BuildRequires: python2-devel
BuildRequires: %server2_both_requires %python2-psycopg2
%endif


Requires:   %default_python-%srcname = %version-%release

Source0:    %{name}-%{version}.tar.gz
Source1:    resalloc.service

%description
Client/Server application for managing of (expensive) resources.

%package server
Summary:    Resource Allocator - Server
Requires:   %default_python-%srcname = %version-%release
Requires:   %server_both_requires
Requires(pre): /usr/sbin/useradd /usr/sbin/mkhomedir_helper
%description server
Server side


%if %{with python3}
%package -n python3-%srcname
Summary:    Resource Allocator - Library
%{?python_provide:%python_provide python3-%srcname}
%description -n python3-%srcname
Libraries.
%endif


%if %{with python2}
%package -n python2-%srcname
Summary:    Resource Allocator - Library
%{?python_provide:%python_provide python2-%srcname}
%description -n python2-%srcname
Libraries.
%endif


%prep
%setup -q


%build
%if %{with python2}
%py2_build
%endif
%if %{with python3}
%py3_build
%endif


%install
%if %{with python2}
%py2_install
%endif
%if %{with python3}
%py3_install
%endif

for sitelib in %default_drop_sitelib; do
    /bin/rm -rf %buildroot$sitelib/%{name}server
done

mkdir -p %buildroot%_unitdir
mkdir -p %buildroot%_logdir
mkdir -p %buildroot%_sharedstatedir/%{name}server
install -p -m 644 %SOURCE1 %buildroot%_unitdir


%if %{with check}
%check
set --
%if %{with python2}
set -- "$@" python2
%endif
%if %{with python3}
set -- "$@" python3
%endif %{with python3}

make check TEST_PYTHONS="$*"
%endif


%pre server
user=%sysuser
group=%sysgroup
getent group "$user" >/dev/null || groupadd -r "$group"
getent passwd "$user" >/dev/null || \
useradd -r -g "$group" -G "$group" -s /bin/bash \
        -c "resalloc server's user" "$user"

# Meh, we often run ansible scripts by cmd_new etc., and ansible needs
# write-able home directory (local_tmp/remote_tmp ansible settings is buggy).
usermod -d "/home/$user" "$user"
mkhomedir_helper "$user" 0007 || :
# Simplify "alembic upgrade head" actions.
ln -sf "%{default_sitelib}/%{name}server" /home/$user/project


%post server
%systemd_post resalloc.service

%postun server
%systemd_postun_with_restart resalloc.service


%files
%license COPYING
%doc README
%{_bindir}/%{name}
%_mandir/man1/%{name}.1*


%if %{with python3}
%files -n python3-%srcname
%doc README
%license COPYING
%{python3_sitelib}/%{name}
%{python3_sitelib}/%{name}-*.egg-info
%endif


%if %{with python2}
%files -n python2-%srcname
%doc README
%license COPYING
%{python2_sitelib}/%{name}
%{python2_sitelib}/%{name}-*.egg-info
%endif


%files server
%doc README
%license COPYING
%{default_sitelib}/%{name}server
%{_bindir}/%{name}-server
%{_bindir}/%{name}-maint
%attr(0700, %sysuser, %sysgroup) %dir %{_sysconfdir}/%{name}server
%config(noreplace) %{_sysconfdir}/%{name}server/*
%_unitdir/resalloc.service
%attr(0700, %sysuser, %sysgroup) %dir %_logdir
%_mandir/man1/%{name}-maint.1*
%attr(0700, %sysuser, %sysgroup) %_sharedstatedir/%{name}server


%changelog
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
