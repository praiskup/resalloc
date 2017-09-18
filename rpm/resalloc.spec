%global srcname resalloc
%global postrel .dev0

Name:       %srcname
Summary:    Resource allocator - Client
Version:    0%{?postrel}
Release:    1%{?dist}
License:    GPLv2+
URL:        https://github.com/praiskup/resalloc
BuildArch:  noarch

Requires:   python3-%srcname
BuildRequires: python3-setuptools python3-devel

Source0:       %{name}-%{version}.tar.gz

%description
Client/Server application for managing of (expensive) resources.

%package server
Summary:    Resource Allocator - Server
Requires:   python3-%srcname
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
find %buildroot


%check


%files
%license COPYING
%{_bindir}/%{name}


%files -n python3-%srcname
%license COPYING
%{python3_sitelib}/%{name}
%{python3_sitelib}/%{name}-*.egg-info


%files server
%license COPYING
%{python3_sitelib}/%{name}server
%{_bindir}/%{name}-server


%changelog
* Mon Sep 18 2017 Pavel Raiskup <praiskup@redhat.com>
- no changelog
