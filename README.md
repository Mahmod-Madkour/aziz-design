# AZIZ DESIGN — Portfolio

Portfolio website for AZIZ DESIGN. Every folder inside `projects/` becomes its own
section on the site. Each project shows 3 of its images; the third one shows "+N"
and opens the rest. Any image opens full screen. The site is available in
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

`cover` is the image shown large in the project's 3-image preview. Without it, the first image is used.

## Many projects (20–50 or more)

The site is built for this:

- The page shows 8 projects, then a **Show more projects** button.
- Each project's `category` becomes a filter button at the top of the work section
  (shown once there are at least 2 different categories). Use exactly the same
  category name in every project that belongs to it.
- A **search** box appears once there are 7 or more projects. It searches titles,
  categories, locations and years in both languages.
- Images are published as small WebP copies (about 150 KB each), so even 50 projects
  stay far below GitHub Pages' 1 GB limit.

To keep the GitHub repository light, export images at about **2500–3000 px** wide
before adding them (a 2 MB JPG is plenty). The build warns about files over 25 MB,
and GitHub refuses files over 100 MB.

## Edit the site text and contact details

Everything outside the projects (headline, about text, services, email,
WhatsApp, Facebook, address…) is in `site.json`. Leave a contact field empty (`""`)
to hide it. Put `*stars*` around a word in the headline to highlight it.
`copyright` is the name shown in the footer's © line (the site name if empty).

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
