Resource Allocator
==================

This project aims to help with taking care of (rather expensive)
resources, for example several ephemeral virtual machines for the purposes
of your CI.

Overview
--------

Server side allows you to:
  - automatically allocate resources
  - periodically check that the resources are working properly
  - and once the resource is not needed anymore, dispose it

The client side let's your users:
  - request particular resource type
  - wait till the resource is available
  - release the resource

Such allocation of resource might be time consuming, so to not let your
users wait too much -- the server side is able to pre-allocate several
instances in advance.  For more info, have a look at `./config/pools.yaml`
configuration example.


What do you mean by resources?
------------------------------

Resalloc's concept of _resources_ is intentionally vague and general. Whatever
your allocation scripts spawn and return to resalloc, those are your
_resources_. It can be virtual machines, docker containers, IP addresses, disk
volumes, or in an extreme case even people (imagine a ticket system at the post
office).

There already are allocation scripts for various kinds of resources:

- [resalloc-aws](https://github.com/praiskup/resalloc-aws) -
  Allocates VMs in the Amazon EC2 cloud
- [resalloc-ibm-cloud](https://github.com/fedora-copr/resalloc-ibm-cloud) -
  Allocates VMs in the IBM Cloud
- [resalloc-openstack](https://github.com/praiskup/resalloc-openstack) -
  Allocates VMs in your OpenStack instance
- [resalloc-kubernetes](https://github.com/TommyLike/resalloc-kubernetes) -
  Allocates pods in your Kubernetes cluster

If you can, please share your own.


Typical client use-cases
------------------------

1. Ask for a resource, and wait till it is ready

```
$ ticket=$(resalloc ticket --tag x86_64 --tag jenkins_vm)
$ output=$(resalloc ticket-wait $ticket)
```

2. get the resource, and periodically check till it is available

```
$ ticket=$(resalloc ticket --tag x86_64 --tag jenkins_vm)
$ while ! resalloc ticket-check $ticket; do true; done
$ output=$(resalloc ticket-check $ticket)
```

Then, you can work with the resource:

```
$ ip=$output
$ ssh root@"$ip" -c "do something"
$ resalloc ticket-close "$ticket"
```

The `$output` variable will contain important info from the `cmd_new`
command run by resalloc server.  If you request VMs, you typically want
`cmd_new` command which outputs an IP of the allocated virtual machine.

Installation
------------

The released versions are installable from Fedora and Fedora EPEL repositories,
just do

```
$ sudo dnf install -y resalloc        # clients
$ sudo dnf install -y resalloc-server # server
```

Pre-release RPMs are available in testing Copr repositories:
https://copr.fedorainfracloud.org/coprs/praiskup/resalloc/
