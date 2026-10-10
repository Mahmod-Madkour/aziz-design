#!/usr/bin/env python3
"""Build the AZIZ DESIGN portfolio website.

Every folder inside projects/ becomes its own section on the site. This script
scans those folders, makes web-sized copies of the images and writes the
finished website into _site/ (that folder is what gets published).

    python3 build.py            build the site into _site/
    python3 build.py --serve    build, then preview it at http://localhost:8000
"""

import argparse
import hashlib
import html
import json
import os
import re
import shutil
import sys
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import quote

try:
    from PIL import Image, ImageOps

    Image.MAX_IMAGE_PIXELS = None  # large renders are expected, and they are our own files
except ImportError:  # the site still builds, just without resizing
    Image = None

ROOT = Path(__file__).resolve().parent
PROJECTS = ROOT / "projects"
OUT = ROOT / "_site"

RESIZABLE = {".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff", ".bmp"}
COPY_AS_IS = {".gif", ".svg", ".avif"}  # animations / vectors are published untouched

FULL_PX = 2400  # longest edge of the image shown in the full-screen viewer
THUMB_PX = 960  # width of the gallery thumbnails
SETTINGS = f"{FULL_PX}-{THUMB_PX}-v1"  # changing this regenerates every image


def natural_key(name):
    """Sort "2.jpg" before "10.jpg"."""
    return [int(part) if part.isdigit() else part.lower() for part in re.split(r"(\d+)", name)]


def read_json(path, required=False):
    if not path.exists():
        if required:
            sys.exit(f"Missing file: {path.relative_to(ROOT)}")
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as err:
        sys.exit(f"Error in {path.relative_to(ROOT)} (line {err.lineno}): {err.msg}")


def localized(value):
    """Accept "text" or {"en": ..., "ar": ...}; always return {"en", "ar"} (or None if empty)."""
    if isinstance(value, dict):
        en = str(value.get("en") or "").strip()
        ar = str(value.get("ar") or "").strip()
    else:
        en = ar = str(value or "").strip()
    if not (en or ar):
        return None
    return {"en": en or ar, "ar": ar or en}


def title_from_folder(name):
    """"01-modern-villa" -> "Modern Villa"."""
    name = re.sub(r"^\d+[\s._-]*", "", name) or name
    name = re.sub(r"[_-]+", " ", name).strip()
    return name.title() if name.islower() else name


def unique_slug(name, used):
    slug = re.sub(r"^\d+[\s._-]*", "", name) or name
    slug = re.sub(r"[^\w]+", "-", slug.lower()).strip("-") or "project"
    base, n = slug, 2
    while slug in used:
        slug, n = f"{base}-{n}", n + 1
    used.add(slug)
    return slug


def url_for(path):
    return "/".join(quote(part) for part in path.relative_to(OUT).parts)


def file_digest(path):
    digest = hashlib.sha1(SETTINGS.encode())
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()[:10]


def to_rgb(im):
    """JPEG has no transparency: put transparent images on a white background."""
    if im.mode == "RGB":
        return im
    im = im.convert("RGBA")
    flat = Image.new("RGB", im.size, "white")
    flat.paste(im, mask=im.getchannel("A"))
    return flat


def web_image(src, dest_dir, written):
    """Write the full-size and thumbnail versions of one image and describe them.

    File names include a hash of the image content, so unchanged images are
    not processed again and visitors' browsers never show an outdated copy.
    """
    stem = re.sub(r"[^\w-]+", "-", src.stem).strip("-").lower() or "image"
    digest = file_digest(src)
    ext = src.suffix.lower()

    if Image is None or ext in COPY_AS_IS:
        out = dest_dir / f"{stem}.{digest}{ext}"
        if not out.exists():
            shutil.copy2(src, out)
        written.add(out)
        return {"src": url_for(out), "thumb": url_for(out)}

    full = dest_dir / f"{stem}.{digest}.jpg"
    thumb = dest_dir / f"{stem}.{digest}.thumb.jpg"
    written.update((full, thumb))
    if full.exists() and thumb.exists():
        with Image.open(full) as im:
            width, height = im.size
        with Image.open(thumb) as im:
            thumb_width = im.width
    else:
        with Image.open(src) as original:
            # keep the colour profile so renders look the same as on the designer's screen
            icc = original.info.get("icc_profile") if original.mode in ("RGB", "RGBA") else None
            im = to_rgb(ImageOps.exif_transpose(original))
        big = im.copy()
        big.thumbnail((FULL_PX, FULL_PX), Image.LANCZOS)
        big.save(full, "JPEG", quality=85, optimize=True, progressive=True, icc_profile=icc)
        small = im.copy()
        small.thumbnail((THUMB_PX, THUMB_PX * 4), Image.LANCZOS)
        small.save(thumb, "JPEG", quality=80, optimize=True, progressive=True, icc_profile=icc)
        width, height, thumb_width = big.width, big.height, small.width
    return {"src": url_for(full), "thumb": url_for(thumb), "w": width, "h": height, "tw": thumb_width}


def load_site():
    raw = read_json(ROOT / "site.json", required=True)
    site = {"name": str(raw.get("name") or "AZIZ DESIGN").strip()}
    for key in ("role", "headline", "intro", "about", "location"):
        site[key] = localized(raw.get(key))
    site["services"] = [s for s in map(localized, raw.get("services") or []) if s]
    contact = raw.get("contact") or {}
    site["contact"] = {key: str(value).strip() for key, value in contact.items() if str(value or "").strip()}
    return site


def load_projects(written):
    """Turn every folder in projects/ into a project with its images."""
    PROJECTS.mkdir(exist_ok=True)
    folders = sorted(
        (d for d in PROJECTS.iterdir() if d.is_dir() and not d.name.startswith((".", "_"))),
        key=lambda d: natural_key(d.name),
    )
    projects, used = [], set()
    for folder in folders:
        info = read_json(folder / "info.json")
        files = sorted(
            (
                f
                for f in folder.iterdir()
                if f.is_file() and not f.name.startswith(".") and f.suffix.lower() in RESIZABLE | COPY_AS_IS
            ),
            key=lambda f: natural_key(f.name),
        )
        if not files:
            print(f"  - {folder.name}/ skipped (no images)")
            continue

        cover = info.get("cover")
        if cover:
            match = next((f for f in files if f.name == cover), None)
            if match:
                files.remove(match)
                files.insert(0, match)
            else:
                print(f"  ! {folder.name}/info.json: cover image \"{cover}\" not found, using the first image")

        slug = unique_slug(folder.name, used)
        dest = OUT / "projects" / slug
        dest.mkdir(parents=True, exist_ok=True)
        images = []
        for f in files:
            try:
                images.append(web_image(f, dest, written))
            except Exception as err:  # one broken file should not stop the whole site
                print(f"  ! could not read {folder.name}/{f.name}: {err}")
        if not images:
            continue

        projects.append(
            {
                "id": slug,
                "title": localized(info.get("title")) or localized(title_from_folder(folder.name)),
                "category": localized(info.get("category")),
                "location": localized(info.get("location")),
                "year": str(info.get("year") or "").strip() or None,
                "description": localized(info.get("description")),
                "images": images,
                "_cover": files[0],
            }
        )
        print(f"  - {folder.name}/ -> {len(images)} images")
    return projects


def remove_stale(written):
    """Delete generated images whose source was removed or changed."""
    for path in sorted((OUT / "projects").rglob("*"), reverse=True):
        if path.is_file() and path not in written:
            path.unlink()
        elif path.is_dir() and not any(path.iterdir()):
            path.rmdir()


def make_share_image(projects):
    """og.jpg: the preview picture shown when the link is shared on WhatsApp, LinkedIn..."""
    target = OUT / "og.jpg"
    if Image is None or not projects or projects[0]["_cover"].suffix.lower() not in RESIZABLE:
        target.unlink(missing_ok=True)
        return False
    with Image.open(projects[0]["_cover"]) as original:
        im = to_rgb(ImageOps.exif_transpose(original))
    ImageOps.fit(im, (1200, 630), Image.LANCZOS).save(target, "JPEG", quality=85, optimize=True)
    return True


def write_index(site, has_share_image, version):
    site_url = (os.environ.get("SITE_URL") or "").rstrip("/")
    role = (site["role"] or {}).get("en")
    title = f"{site['name']} — {role}" if role else site["name"]
    description = ((site["intro"] or site["headline"]) or {}).get("en", "").replace("*", "")
    share_image = ""
    if has_share_image:
        share_image = f"{site_url}/og.jpg?v={version}" if site_url else "og.jpg"
    values = {
        "title": title,
        "description": description,
        "site_url": f"{site_url}/" if site_url else "",
        "share_image": share_image,
        "version": version,
    }
    page = (ROOT / "index.html").read_text(encoding="utf-8")
    for key, value in values.items():
        page = page.replace("{{" + key + "}}", html.escape(value, quote=True))
    (OUT / "index.html").write_text(page, encoding="utf-8")


def serve(port):
    class QuietHandler(SimpleHTTPRequestHandler):
        def log_message(self, *args):
            pass

    with ThreadingHTTPServer(("127.0.0.1", port), partial(QuietHandler, directory=str(OUT))) as server:
        print(f"\nPreview: http://localhost:{port}   (press Ctrl+C to stop)")
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print()


def main():
    parser = argparse.ArgumentParser(description="Build the AZIZ DESIGN portfolio website.")
    parser.add_argument("--serve", action="store_true", help="preview the site after building it")
    parser.add_argument("--port", type=int, default=8000, help="port for --serve (default 8000)")
    args = parser.parse_args()

    if Image is None:
        print("Note: Pillow is not installed, so images are published without resizing.")
        print("      Install it with:  pip install pillow\n")

    site = load_site()
    OUT.mkdir(exist_ok=True)
    shutil.rmtree(OUT / "assets", ignore_errors=True)
    shutil.copytree(ROOT / "assets", OUT / "assets")

    print("Projects:")
    written = set()
    projects = load_projects(written)
    remove_stale(written)
    has_share_image = make_share_image(projects)
    for project in projects:
        del project["_cover"]

    data = json.dumps({"site": site, "projects": projects}, ensure_ascii=False, indent=1)
    (OUT / "data.js").write_text(f"window.AZIZ_DATA = {data};\n", encoding="utf-8")

    version = hashlib.sha1(data.encode())
    for asset in sorted((ROOT / "assets").rglob("*")):
        if asset.is_file():
            version.update(asset.read_bytes())
    write_index(site, has_share_image, version.hexdigest()[:8])

    total = sum(len(p["images"]) for p in projects)
    print(f"\nDone: {len(projects)} projects, {total} images -> {OUT.name}/")
    samples = [key for key, value in site["contact"].items() if "example" in value or "000 0000" in value]
    if samples:
        print(f"Reminder: site.json still has sample contact details ({', '.join(samples)}).")

    if args.serve:
        serve(args.port)


if __name__ == "__main__":
    main()
