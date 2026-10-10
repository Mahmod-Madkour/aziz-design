# AZIZ DESIGN — Portfolio

Portfolio website for AZIZ DESIGN. Every folder inside `projects/` becomes its own
section on the site, with a gallery of its images. The site is available in
English and Arabic.

## Add or change a project

1. Create a folder inside `projects/`, for example `projects/04-sea-view-villa/`.
2. Put the project's images in it (`.jpg`, `.png`, `.webp`…). Large files are fine:
   the build makes web-sized copies automatically.
3. Optional: add an `info.json` file in the folder for titles and details
   (copy one from `projects/01-project-one/`).

That's all. To remove a project, delete its folder.

**Order:** projects are sorted by folder name, so start names with `01-`, `02-`, `03-`…
The number is not shown on the site. Images are sorted by file name in the same way.

**Without `info.json`** the title comes from the folder name
(`04-sea-view-villa` → "Sea View Villa") and is the same in both languages.

### `info.json` fields (all optional)

```json
{
  "title":       { "en": "Sea View Villa", "ar": "فيلا على البحر" },
  "category":    { "en": "Interior Design", "ar": "تصميم داخلي" },
  "location":    { "en": "Alexandria", "ar": "الإسكندرية" },
  "year":        "2025",
  "cover":       "05.jpg",
  "description": { "en": "Text in English…", "ar": "النص بالعربية…" }
}
```

`cover` is the image shown first and on the project card. Without it, the first image is used.

## Edit the site text and contact details

Everything outside the projects (headline, about text, services, email,
WhatsApp, Instagram…) is in `site.json`. Leave a contact field empty (`""`)
to hide it. Put `*stars*` around a word in the headline to highlight it.

## Preview on your computer

```bash
pip install pillow          # once
python3 build.py --serve    # then open http://localhost:8000
```

## Publish

The site is hosted on GitHub Pages. Pushing to the `main` branch rebuilds and
publishes it automatically (see `.github/workflows/deploy.yml`):

```bash
git add .
git commit -m "Add new project"
git push
```

The site updates about one minute after the push.

**First-time setup on GitHub:** the repository must be public (GitHub Pages is free for public
repositories). In the repository, go to **Settings → Pages → Build and deployment → Source** and
choose **GitHub Actions**.

## Files

| Path | What it is |
| --- | --- |
| `projects/` | one folder per project, with its images and optional `info.json` |
| `site.json` | site text and contact details |
| `index.html`, `assets/` | page layout, styles and script |
| `build.py` | turns the folders into the website (output in `_site/`) |
