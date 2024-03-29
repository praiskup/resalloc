%global		_source_filedigest_algorithm md5

%global scriptname build-resalloc
%global obsdir /usr/lib/obs/service

Name:		obs-service-build-resalloc
Version:	1
Release:	1%{?dist}
Summary:	OBS resalloc builder
BuildArch:	noarch

Group:		NONE
License:	GPLv3+
URL:		http://example.com/

# Needed for the script runtime (i.e. resalloc's build-time).
Requires:	bsdtar
Requires:	make
Requires:	python3-setuptools

%if 0%{?rhel} && 0%{?rhel} <= 5
BuildRoot:	%{_tmppath}/%{name}-%{version}-%{release}-root-%(%{__id_u} -n)
%endif
Source0:	script

%{!?_pkgdocdir: %global _pkgdocdir %{_docdir}/%{name}-%{version}}

%description
Package bringing %_bindir/%scriptname script for OBS builds.


%prep


%build


%install
rm -rf $RPM_BUILD_ROOT
mkdir -p $RPM_BUILD_ROOT/%_bindir
mkdir -p $RPM_BUILD_ROOT/%obsdir
install -m 0755 %SOURCE0 $RPM_BUILD_ROOT/%obsdir/%scriptname
ln -s -T %obsdir/%scriptname $RPM_BUILD_ROOT/%_bindir/%scriptname


%clean
rm -rf $RPM_BUILD_ROOT


%files
%_bindir/*
/usr/lib/obs
/usr/lib/obs/service

%changelog
* Mon Aug 30 2021 Pavel Raiskup <praiskup@redhat.com> - 1-1
- no changelog
