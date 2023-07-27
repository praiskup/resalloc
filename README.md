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


Motivation
----------

At the first sight, it may look like resource allocation is a simple task
and using something like resalloc is an overkill. But please consider what
resalloc can do for you and what you would eventually need to implement on your
own when starting from scratch.

- Multiple resource pools - Resalloc allows to define multiple pools of
  resources. They can either provide identical resources or different
  kinds of resources (e.g. x86_64 VMs from Amazon AWS and x86_64 VMs from
  OpenStack that can be used interchangeably, and ppc64le VMs from IBM Cloud
  that are used for a different purpose).
- Client-server architecture - Allocating many new resources in parallel can be
  surprisingly heavy on CPU and memory, so it can be useful to dedicate a
  separate machine to resource allocation.
- Gradual allocation - Allocating resources on self-hosted hardware is for free,
  so it makes sense to use it to the full capacity at all times. However,
  somebody will have to pay for every allocated resource in the cloud, so we
  want to allocate only as much resources as we need at the moment.
- Preallocation - Allocating new resources can take some time (e.g. spawning a
  new VM in the cloud and running ansible playbooks to provision it can take few
  minutes), and users don't want to wait. It is a good idea to preallocate a
  small number of resources that are ready to be used immediately.
- Livechecks - Clouds are unreliable. VMs can break while starting or become
  unresponsive for various reasons. Resalloc periodically checks the livelines
  of all resources and makes sure money doesn't leak out of our pockets.
- Resource prioritization - Multiple pools can provide the same resources but
  they might not cost the same. There is a price for running VMs in Amazon
  AWS. The same VMs as Spot instances are a bit cheaper, and running them on a
  self-hosted sever is for free. Resalloc prioritizes to be wallet-friendly.
- Web interface - It is possible to optionally run a web UI and let users see
  what, and how many resources are available. For example, see
  [Copr resources](https://download.copr.fedorainfracloud.org/resalloc).

Resalloc was created to accomodate the ever growing
[farm of Copr builders](https://pavel.raiskup.cz/blog/copr-farm-of-builders.html).


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
