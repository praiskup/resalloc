- [ ] documentation
- [x] - README
- [ ] travis CI
- [ ]   testsuite
- [ ] user support (authentication?)
- [ ] completely "detached" allocator/terminator
- [ ] track pools completely in database (and bound it with 1:N relation with
      resources);  otherwise manager looses info about resources if the pool ID
      is changed in configuration file (no cmd_delete, etc.).  It is then very
      difficult to even terminate the resource.
- [ ] add on-demand started resources;  those which nave 0 preallocated
      instances, but start if there's ticket for them
- [x] packaging for EPEL7
- [x] systemd service file
- [x] config
- [x] - default configuration files
- [ ] PLACEHOLDER
