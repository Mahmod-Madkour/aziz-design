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
from concurrent.futures import ProcessPoolExecutor
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import quote

try:
    from PIL import Image, ImageOps, features

    Image.MAX_IMAGE_PIXELS = None  # large renders are expected, and they are our own files
except ImportError:  # the site still builds, just without resizing
    Image = None

ROOT = Path(__file__).resolve().parent
PROJECTS = ROOT / "projects"
OUT = ROOT / "_site"

RESIZABLE = {".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff", ".bmp"}
COPY_AS_IS = {".gif", ".svg", ".avif"}  # animations / vectors are published untouched

FULL_PX = 2200  # longest edge of the image shown in the full-screen viewer
THUMB_PX = 900  # width of the gallery thumbnails
# WebP files are about a third smaller than JPEG, which keeps 50 projects well under
# GitHub Pages' 1 GB limit. Older Pillow builds without WebP fall back to JPEG.
WEBP = Image is not None and features.check("webp")
EXT = ".webp" if WEBP else ".jpg"
SETTINGS = f"{FULL_PX}-{THUMB_PX}-{EXT}-v2"  # changing this regenerates every image

BIG_FILE = 25 * 1024 * 1024  # source images above this make the GitHub repository heavy
GITHUB_LIMIT = 100 * 1024 * 1024  # GitHub refuses files above this


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
    """Web images need plain RGB: put transparent images on a white background."""
    if im.mode == "RGB":
        return im
    im = im.convert("RGBA")
    flat = Image.new("RGB", im.size, "white")
    flat.paste(im, mask=im.getchannel("A"))
    return flat


def save(im, path, quality, icc):
    if WEBP:
        im.save(path, "WEBP", quality=quality, method=4, icc_profile=icc)
    else:
        im.save(path, "JPEG", quality=quality, optimize=True, progressive=True, icc_profile=icc)


def process_image(src, dest_dir):
    """Write the full-size and thumbnail versions of one image and describe them.

    Runs in a separate process (several images at once). File names include a
    hash of the image content, so unchanged images are not processed again and
    visitors' browsers never show an outdated copy.
    Returns (image info, files written, error message).
    """
    try:
        stem = re.sub(r"[^\w-]+", "-", src.stem).strip("-").lower() or "image"
        digest = file_digest(src)
        ext = src.suffix.lower()

        if Image is None or ext in COPY_AS_IS:
            out = dest_dir / f"{stem}.{digest}{ext}"
            if not out.exists():
                shutil.copy2(src, out)
            return {"src": url_for(out), "thumb": url_for(out)}, [out], None

        full = dest_dir / f"{stem}.{digest}{EXT}"
        thumb = dest_dir / f"{stem}.{digest}.thumb{EXT}"
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
            save(big, full, 82, icc)
            small = im.copy()
            small.thumbnail((THUMB_PX, THUMB_PX * 4), Image.LANCZOS)
            save(small, thumb, 78, icc)
            width, height, thumb_width = big.width, big.height, small.width
        info = {"src": url_for(full), "thumb": url_for(thumb), "w": width, "h": height, "tw": thumb_width}
        return info, [full, thumb], None
    except Exception as err:  # one broken file should not stop the whole site
        return None, [], str(err)


def load_site():
    raw = read_json(ROOT / "site.json", required=True)
    site = {"name": str(raw.get("name") or "AZIZ DESIGN").strip()}
    site["copyright"] = str(raw.get("copyright") or "").strip() or site["name"]
    for key in ("role", "headline", "intro", "about", "location"):
        site[key] = localized(raw.get(key))
    site["services"] = [s for s in map(localized, raw.get("services") or []) if s]
    contact = raw.get("contact") or {}
    site["contact"] = {key: str(value).strip() for key, value in contact.items() if str(value or "").strip()}
    return site


def find_projects(warnings):
    """Every folder in projects/ with its info.json and its image files, in order."""
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
                warnings.append(f"{folder.name}/info.json: cover image \"{cover}\" not found, using the first image")

        for f in files:
            size = f.stat().st_size
            if size > GITHUB_LIMIT:
                warnings.append(f"{folder.name}/{f.name} is {size >> 20} MB: GitHub refuses files over 100 MB, export it smaller")
            elif size > BIG_FILE:
                warnings.append(f"{folder.name}/{f.name} is {size >> 20} MB: exporting it at ~3000 px keeps the repository light")

        projects.append({"folder": folder, "info": info, "files": files, "slug": unique_slug(folder.name, used)})
    return projects


def process_all(found, warnings):
    """Resize all images (several at once) and return the projects for data.js."""
    jobs = []
    for project in found:
        dest = OUT / "projects" / project["slug"]
        dest.mkdir(parents=True, exist_ok=True)
        jobs += [(project, f, dest) for f in project["files"]]

    with ProcessPoolExecutor() as pool:
        results = list(pool.map(process_image, [j[1] for j in jobs], [j[2] for j in jobs], chunksize=4))

    written, images_of = set(), {id(p): [] for p in found}
    for (project, src, _), (info, outputs, error) in zip(jobs, results):
        written.update(outputs)
        if error:
            warnings.append(f"could not read {project['folder'].name}/{src.name}: {error}")
        else:
            images_of[id(project)].append(info)

    projects = []
    for project in found:
        images, info, folder = images_of[id(project)], project["info"], project["folder"]
        print(f"  - {folder.name}/ -> {len(images)} images")
        if not images:
            continue
        projects.append(
            {
                "id": project["slug"],
                "title": localized(info.get("title")) or localized(title_from_folder(folder.name)),
                "category": localized(info.get("category")),
                "location": localized(info.get("location")),
                "year": str(info.get("year") or "").strip() or None,
                "description": localized(info.get("description")),
                "images": images,
            }
        )
    return projects, written


def remove_stale(written):
    """Delete generated images whose source was removed or changed."""
    for path in sorted((OUT / "projects").rglob("*"), reverse=True):
        if path.is_file() and path not in written:
            path.unlink()
        elif path.is_dir() and not any(path.iterdir()):
            path.rmdir()


def make_share_image(found):
    """og.jpg: the preview picture shown when the link is shared on WhatsApp, LinkedIn..."""
    target = OUT / "og.jpg"
    cover = found[0]["files"][0] if found else None
    if Image is None or cover is None or cover.suffix.lower() not in RESIZABLE:
        target.unlink(missing_ok=True)
        return False
    with Image.open(cover) as original:
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
    warnings = []
    found = find_projects(warnings)
    projects, written = process_all(found, warnings)
    remove_stale(written)
    has_share_image = make_share_image(found)

    data = json.dumps({"site": site, "projects": projects}, ensure_ascii=False, separators=(",", ":"))
    (OUT / "data.js").write_text(f"window.AZIZ_DATA = {data};\n", encoding="utf-8")

    version = hashlib.sha1(data.encode())
    for asset in sorted((ROOT / "assets").rglob("*")):
        if asset.is_file():
            version.update(asset.read_bytes())
    write_index(site, has_share_image, version.hexdigest()[:8])

    total = sum(len(p["images"]) for p in projects)
    size = sum(f.stat().st_size for f in OUT.rglob("*") if f.is_file())
    print(f"\nDone: {len(projects)} projects, {total} images -> {OUT.name}/ ({size / 1024 / 1024:.0f} MB)")
    for warning in warnings:
        print(f"  ! {warning}")
    samples = [key for key, value in site["contact"].items() if "example" in value or "000 0000" in value]
    if samples:
        print(f"Reminder: site.json still has sample contact details ({', '.join(samples)}).")

    if args.serve:
        serve(args.port)


if __name__ == "__main__":
    main()
