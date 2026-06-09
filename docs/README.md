# Documentation (docs/)

This folder hosts a simple static docs site (HTML + CSS) intended to be served by GitHub Pages from the `docs/` directory.

Structure:
- `index.html` — Home page and quick intro
- `getting-started.html` — Install and quick run instructions (placeholders)
- `architecture.html` — Project layout overview
- `style.css` — Simple site stylesheet

How to publish (quick):
1. Commit these files and push to the `main` branch.
2. In your repository settings on GitHub: Settings → Pages → Source: `main` branch / `docs/` folder. Save.
3. After a few minutes your site will be available at `https://<github-username>.github.io/pybullet-swarm-sim`.

Custom domain (optional):
- Create a `CNAME` file at `docs/CNAME` with your domain (e.g. `myname.pybullet-swarm-sim.io`).
- Add DNS `A` or `CNAME` records as instructed by GitHub Pages docs.

Local preview:
- You can preview these files locally by opening `docs/index.html` in any browser. For a local server run:

```bash
# Python 3
cd docs
python -m http.server 8000
# then visit http://localhost:8000
```

Fill the HTML files with your content and images in `docs/images` (or reference files from the repo root). If you prefer markdown-driven sites, consider switching to MkDocs or Jekyll later.