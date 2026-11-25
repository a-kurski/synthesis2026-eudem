# DTM workflow server environment setup

Environment record for running the Rhine catchment DTM preparation workflow on the Linux server.

## 1. Purpose

A Python virtual environment was created in the repository root to run the DTM acquisition and processing workflow. The server already provided Python and the GDAL command-line installation, but the Python GDAL bindings were not available to the system Python. The virtual environment therefore contains the Python dependencies required by the workflow, including GDAL bindings matched to the installed GDAL version.

## 2. Existing server software

Administrative access: the user account does not have `sudo` privileges, so no system packages were installed during this setup.

| Component | Version / location | Status |
| --- | --- | --- |
| Python | 3.12.3; `/usr/bin/python3` | Already installed |
| GDAL CLI | 3.12.1 "Chicoutimi"; `/usr/local/bin/gdalinfo` | Already installed |
| GDAL headers | `/usr/local/include` | Available |
| GDAL library | `/usr/local/lib`; `-lgdal` | Available |
| Python `osgeo` bindings | Not available in system Python | Installed later in venv |

## 3. Virtual environment

The virtual environment was created at the root of the cloned repository:

```bash
cd ~/synthesis2026-eudem
python3 -m venv .venv
source .venv/bin/activate
```

The active Python executable was verified as:

```text
/home/ardabaysal/synthesis2026-eudem/.venv/bin/python
```

## 4. Python dependencies installed in the venv

Packaging tools were upgraded first:

```bash
python -m pip install --upgrade pip setuptools wheel
```

The workflow dependencies were then installed:

```bash
pip install numpy requests
pip install "GDAL==3.12.1"
```

The GDAL Python package was pinned to 3.12.1 to match the GDAL 3.12.1 library already installed on the server. The wheel was built successfully against the available GDAL headers and library.

| Runtime package | Installed version |
| --- | --- |
| NumPy | 2.5.3 |
| Requests | 2.34.2 |
| GDAL Python bindings | 3.12.1 |

## 5. Verification

The Python dependencies were verified with:

```bash
python -c "import numpy, requests; from osgeo import gdal, ogr, osr; print('NumPy:', numpy.__version__); print('Requests:', requests.__version__); print(gdal.VersionInfo('--version')); print('All Python dependencies OK')"
```

The resulting versions were:

```text
NumPy: 2.5.3
Requests: 2.34.2
GDAL 3.12.1 "Chicoutimi", released 2025/12/12 (debug build)
All Python dependencies OK
```

The GDAL command-line utilities required by the workflow were also verified:

```bash
gdalinfo --version
gdalwarp --version
gdalbuildvrt --version
gdal_translate --version
```

All four commands reported GDAL 3.12.1.

## 6. Final setup

The workflow now runs with a repository-local Python virtual environment while using the GDAL installation already present on the server. The GDAL command-line tools remain system executables, while NumPy, Requests and the matching GDAL Python bindings are installed inside `.venv`. No QGIS or OSGeo4W installation is required on the Linux server.

For a new shell session, activate the environment before running the workflow:

```bash
cd ~/synthesis2026-eudem
source .venv/bin/activate
```

The environment is then ready for commands run from the repository or `pipeline` directory, for example:

```bash
cd pipeline
python main.py config.netherlands.json --plan
```
