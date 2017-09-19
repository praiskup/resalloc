%global srcname resalloc
%global postrel .dev0

%global sysuser  resalloc
%global sysgroup %sysuser
%global _logdir  %_var/log/%{name}server

Name:       %srcname
Summary:    Resource allocator - Client
Version:    0%{?postrel}
Release:    2%{?dist}
License:    GPLv2+
URL:        https://github.com/praiskup/resalloc
BuildArch:  noarch

Requires:   python3-%srcname = %version-%release
BuildRequires: python3-setuptools python3-devel

Source0:    %{name}-%{version}.tar.gz
Source1:    resalloc.service

%description
Client/Server application for managing of (expensive) resources.

%package server
Summary:    Resource Allocator - Server
Requires:   python3-%srcname = %version-%release
%description server
Server side

%package -n python3-%srcname
Summary:    Resource Allocator - Library
%{?python_provide:%python_provide python3-%srcname}
%description -n python3-%srcname
Libraries.

%prep
%setup -q


%build
python3 setup.py build


%install
python3 setup.py install --root=%{buildroot}
mkdir -p %buildroot%_unitdir
mkdir -p %buildroot%_logdir
install -p -m 644 %SOURCE1 %buildroot%_unitdir
find %buildroot


%check


%pre server
user=%sysuser
group=%sysgroup
getent group "$user" >/dev/null || groupadd -r "$group"
getent passwd "$user" >/dev/null || \
useradd -r -g "$group" -G "$group" -s /sbin/nologin \
        -c "resalloc server's user" "$user"


%post server
%systemd_post resalloc.service

%postun server
%systemd_postun_with_restart resalloc.service


%files
%license COPYING
%doc README
%{_bindir}/%{name}


%files -n python3-%srcname
%doc README
%license COPYING
%{python3_sitelib}/%{name}
%{python3_sitelib}/%{name}-*.egg-info


%files server
%doc README
%license COPYING
%{python3_sitelib}/%{name}server
%{_bindir}/%{name}-server
%attr(0700, %sysuser, %sysgroup) %dir %{_sysconfdir}/%{name}server
%config(noreplace) %{_sysconfdir}/%{name}server/*
%_unitdir/resalloc.service
%attr(0700, %sysuser, %sysgroup) %dir %_logdir


%changelog
* Tue Sep 19 2017 Pavel Raiskup <praiskup@redhat.com> - 0.dev0-2
- add service file
- install log directory for server

* Mon Sep 18 2017 Pavel Raiskup <praiskup@redhat.com>
- no changelog
