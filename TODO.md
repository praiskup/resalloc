- [ ] guarantee that new/delete logs don't waste a whole disk
- [ ] documentation
- [x] store new/delete logs
- [x] - README
- [x] travis CI
- [x]   testsuite
- [ ] mock-ed testsuite and coverage
- [ ] test the periodic check cmd
- [ ] user support (authentication?)
- [ ] completely "detached" allocator/terminator
- [ ] track pools completely in database (and bound it with 1:N relation with
      resources);  otherwise manager looses info about resources if the pool ID
      is changed in configuration file (no cmd_delete, etc.).  It is then very
      difficult to even terminate the resource.
- [ ] add on-demand started resources;  those which nave 0 preallocated
      instances, but start if there's ticket for them
- [ ] cmd\_\* actions should be run under different user than 'resalloc' since
      that's pretty privileged user
- [ ] store into db (and print) the startup time/termianting time
- [x] packaging for EPEL7
- [x] systemd service file
- [x] config
- [x] - default configuration files
- [ ] PLACEHOLDER
