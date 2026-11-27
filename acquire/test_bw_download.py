import requests
import zipfile
from pathlib import Path

url = (
    "https://opengeodata.lgl-bw.de/data/dgm/"
    "dgm1_32_557_5434_2_bw.zip"
    "?customerGroup=hochschulen-wissenschaft"
)

destination = Path("bw_test_download.zip")

# Download
with requests.get(url, stream=True, timeout=120) as response:
    response.raise_for_status()
    with destination.open("wb") as file:
        for chunk in response.iter_content(chunk_size=1024 * 1024):
            if chunk:
                file.write(chunk)

print(f"Downloaded: {destination}")

# Verify ZIP contents
with zipfile.ZipFile(destination) as archive:
    print("\nArchive contents:")
    for name in archive.namelist():
        print(name)

    print("ZIP valid:", archive.testzip() is None)