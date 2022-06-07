import os
import sys


# In case we are working within the upstream project, we want to use static
# files and templates from git (for easier development). Otherwise we want to
# use files installed from the RPM package.
here = os.path.abspath(os.path.dirname(__file__))
datadirs = [here, "/usr/share/resallocwebui"]
for datadir in datadirs:
    staticdir = os.path.join(datadir, "static")
    templatedir = os.path.join(datadir, "templates")
    if os.path.isdir(staticdir) and os.path.isdir(templatedir):
        break
else:
    print("Error: Not found any valid data directory")
    sys.exit(1)
