"""Install the fonts used by the shared video style.

    python -m pip install -r font-requirements.txt
    python install_fonts.py --list     # dry run, changes nothing
    python install_fonts.py            # install

Restart Python after installation so Manim can discover the fonts.
"""
import hashlib, io, json, os, platform, re, shutil, subprocess, sys, urllib.request, zipfile

UA = {"User-Agent": "reducible-font-installer"}
WEIGHTS = ("Regular", "Book", "Medium", "SemiBold", "Bold", "Light")
SKIP = re.compile(r"(italic|oblique|variable|display|subhead|smtext|caption|nl-|-it[._-])")

FONTS = [
    ("Inter",           "rsms/inter",               "inter",         lambda n: n.endswith(".zip")),
    ("JetBrains Mono",  "JetBrains/JetBrainsMono",  "jetbrainsmono", lambda n: n.endswith(".zip")),
]

EXCALIFONT_URL = (
    "https://raw.githubusercontent.com/excalidraw/excalidraw/master/"
    "packages/excalidraw/fonts/Excalifont/"
    "Excalifont-Regular-a88b72a24fb54c9f94e3b5fdaa7481c9.woff2"
)
EXCALIFONT_SHA256 = "e4423b318e11432aff2e6e865e300b7ca270f92321a3f56632268fede01c1b48"
EXCALIFONT_FILENAME = "Excalifont-Regular.ttf"


def keep(member, prefix):
    base = os.path.basename(member)
    low = base.lower()
    if not low.endswith((".ttf", ".otf")) or SKIP.search(low):
        return False
    if not low.startswith(prefix):
        return False
    return any(w.lower() in low for w in WEIGHTS)


def dedupe(members):
    """If a family ships both .ttf and .otf of the same style, keep the .ttf."""
    best = {}
    for m in members:
        stem = os.path.splitext(os.path.basename(m))[0].lower()
        if stem not in best or m.lower().endswith(".ttf"):
            best[stem] = m
    return sorted(best.values())


def fetch(url, timeout=180):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
        return r.read()


def latest_zip(repo, pick):
    api = f"https://api.github.com/repos/{repo}/releases/latest"
    rel = json.loads(fetch(api, 60))
    for a in rel.get("assets", []):
        if pick(a["name"]):
            return rel["tag_name"], a["name"], a["browser_download_url"]
    raise RuntimeError(f"no matching .zip asset in {repo} {rel.get('tag_name')}")


def target_dir():
    s = platform.system()
    if s == "Darwin":
        return os.path.expanduser("~/Library/Fonts")
    if s == "Windows":
        return os.path.join(os.environ["LOCALAPPDATA"], "Microsoft", "Windows", "Fonts")
    return os.path.expanduser("~/.local/share/fonts/reducible")


def register_windows(path, stem):
    import winreg
    k = winreg.CreateKey(winreg.HKEY_CURRENT_USER,
                         r"Software\Microsoft\Windows NT\CurrentVersion\Fonts")
    ext = "(TrueType)" if path.lower().endswith(".ttf") else "(OpenType)"
    winreg.SetValueEx(k, f"{stem} {ext}", 0, winreg.REG_SZ, path)
    winreg.CloseKey(k)


def install_excalifont(dest, dry):
    print("Excalifont: official Latin subset (SIL Open Font License 1.1)")
    if dry:
        print(f"  would install {EXCALIFONT_FILENAME}")
        return 1

    try:
        from fontTools.ttLib import TTFont
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "Excalifont conversion needs fonttools; run "
            "`python -m pip install -r font-requirements.txt`."
        ) from exc

    data = fetch(EXCALIFONT_URL)
    digest = hashlib.sha256(data).hexdigest()
    if digest != EXCALIFONT_SHA256:
        raise RuntimeError(f"Excalifont checksum mismatch: {digest}")

    font = TTFont(io.BytesIO(data))
    family = font["name"].getDebugName(1)
    if family != "Excalifont":
        raise RuntimeError(f"Unexpected Excalifont family name: {family!r}")
    font.flavor = None
    converted = io.BytesIO()
    font.save(converted)
    font.close()

    path = os.path.join(dest, EXCALIFONT_FILENAME)
    with open(path, "wb") as target:
        target.write(converted.getvalue())
    if platform.system() == "Windows":
        register_windows(path, os.path.splitext(EXCALIFONT_FILENAME)[0])
    print(f"  installed {EXCALIFONT_FILENAME}")
    return 1


def main():
    dry = "--list" in sys.argv
    dest = target_dir()
    print(f"platform : {platform.system()}\nfonts dir: {dest}\n")
    if not dry:
        os.makedirs(dest, exist_ok=True)
    total = 0
    for name, repo, prefix, pick in FONTS:
        try:
            tag, asset, url = latest_zip(repo, pick)
            print(f"{name}: {tag} / {asset}")
            data = fetch(url)
            z = zipfile.ZipFile(io.BytesIO(data))
            hits = dedupe([m for m in z.namelist() if keep(m, prefix)])
            if not hits:
                print("  !! no static weights found - install this one manually")
                continue
            for m in hits:
                base = os.path.basename(m)
                print(f"  {'would install' if dry else 'installed'} {base}")
                if not dry:
                    out = os.path.join(dest, base)
                    with open(out, "wb") as f:
                        f.write(z.read(m))
                    if platform.system() == "Windows":
                        register_windows(out, os.path.splitext(base)[0])
            total += len(hits)
        except Exception as e:
            print(f"  !! {name} failed: {type(e).__name__}: {e}")
    total += install_excalifont(dest, dry)
    print(f"\n{total} font files {'listed' if dry else 'installed'}.")
    if not dry and shutil.which("fc-cache"):
        subprocess.run(["fc-cache", "-f", dest], check=False)
        print("fontconfig cache rebuilt.")
    print("\nNEXT: close and reopen your terminal / restart Python, then render a preview.")


if __name__ == "__main__":
    main()