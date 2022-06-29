# How to release a new resalloc version

1. Bump `__version__` variable in the `resalloc/__init__.py` file
2. Edit `NEWS` file and write a changelog for this new version
3. Git commit & and push
4. Tag a new version, e.g. `git tag -a v4.4 -m "Release v4.4"`
5. Push the new tag, e.g. `git push origin v4.4 `
6. Create a new release on GitHub - https://github.com/praiskup/resalloc/releases
7. Upload tarball to GitHub. It is generated as a byproduct of `cd rpm && make srpm`
8. Fedora-related actions - koji, infra-tags, bodhi, etc.
