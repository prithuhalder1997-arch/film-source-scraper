# PyInstaller spec — bundles the capture engine into a single native app.
# Build:  pyinstaller packaging/engine.spec
# Output: dist/CaptureEngine  (a folder-app; wrap in .dmg/.exe installer below)
#
# The key trick: Playwright's Chromium is copied INTO the bundle so the end
# user never runs `playwright install`. We locate it at build time and ship it.

import os, pathlib
from PyInstaller.utils.hooks import collect_all

block_cipher = None
HERE = pathlib.Path(os.getcwd())

# locate the Playwright browser cache to bundle Chromium
def find_playwright_browsers():
    candidates = [
        pathlib.Path.home() / ".cache" / "ms-playwright",                 # linux
        pathlib.Path.home() / "Library" / "Caches" / "ms-playwright",     # mac
        pathlib.Path(os.environ.get("LOCALAPPDATA", "")) / "ms-playwright" # win
    ]
    for c in candidates:
        if c.exists():
            return c
    return None

pw = find_playwright_browsers()
extra_datas = []
if pw:
    # ship the whole browser dir; Playwright will find it via env var at runtime
    extra_datas.append((str(pw), "ms-playwright"))

# collect playwright + fastapi + uvicorn packages fully
datas, binaries, hiddenimports = [], [], []
for pkg in ["playwright", "uvicorn", "fastapi", "pydantic"]:
    d, b, h = collect_all(pkg)
    datas += d; binaries += b; hiddenimports += h

datas += extra_datas
# ship the pipeline source alongside the engine
datas += [
    (str(HERE / "scrape.py"), "."),
    (str(HERE / "paywall_agent.py"), "."),
    (str(HERE / "films.json"), "."),
    (str(HERE / "engine" / "launcher.py"), "."),
]

a = Analysis(
    [str(HERE / "engine" / "launcher.py")],
    pathex=[str(HERE)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports + ["scrape", "paywall_agent"],
    hookspath=[], runtime_hooks=[], excludes=[],
    cipher=block_cipher, noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz, a.scripts, [], exclude_binaries=True,
    name="CaptureEngine", debug=False, strip=False, upx=False,
    console=True,   # console shows the "keep me open" message; can hide later
)
coll = COLLECT(
    exe, a.binaries, a.zipas, a.datas, strip=False, upx=False,
    name="CaptureEngine",
)
