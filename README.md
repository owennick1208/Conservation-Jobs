# Field Notices — a personal wildlife & conservation job aggregator

Gathers job openings from several niche conservation boards into one fast,
searchable page that refreshes itself once a day and is served free on GitHub
Pages.

**Sources**
- **TAMU Natural Resources Board** (`jobs.rwfm.tamu.edu`) — the big one: wildlife, fisheries, rangeland, faculty, seasonal.
- **PARC** (`parcplace.org`) — hand-curated reptile & amphibian jobs.
- **U.S. Fish & Wildlife Service** via the official **USAJobs API** (optional — needs a free key, see below).

The webpage links straight to each employer's own application page.

---

## How it fits together

```
scrape.py            # runs every source, merges + dedupes, writes docs/jobs.json
sources/             # one small scraper per site
  parc.py
  tamu.py
  usajobs_fws.py
  util.py
docs/                # this folder is what GitHub Pages serves
  index.html         # the job board (reads jobs.json)
  jobs.json          # the data (seed data now; overwritten on first scrape)
.github/workflows/
  scrape.yml         # the daily auto-refresh
```

The page you see right now is filled with **sample listings** so it isn't empty.
The first real scrape replaces them with live data.

---

## One-time setup (about 15 minutes)

1. **Create a GitHub repo** and upload this folder (or `git push` it).
2. **Turn on Pages:** repo → *Settings* → *Pages* → *Build and deployment* →
   Source: **Deploy from a branch**, Branch: **main**, Folder: **/docs** → *Save*.
   After a minute your board is live at `https://YOUR-USERNAME.github.io/REPO-NAME/`.
3. **Turn on the daily refresh:** the workflow in `.github/workflows/scrape.yml`
   runs automatically. To run it now, go to the *Actions* tab → *Refresh job
   listings* → *Run workflow*. It scrapes and commits an updated `docs/jobs.json`.

That's it for the TAMU and PARC sources.

### Optional: add Fish & Wildlife (USAJobs)

1. Request a free API key at <https://developer.usajobs.gov/apirequest/>.
2. In the repo: *Settings* → *Secrets and variables* → *Actions* → add two secrets:
   - `USAJOBS_API_KEY` — the key they email you
   - `USAJOBS_EMAIL` — the email you registered with
3. The next run will start including FWS postings. Without these, that source is
   simply skipped.

---

## Run it locally (to test before hosting)

```bash
pip install -r requirements.txt
python scrape.py                 # writes docs/jobs.json
cd docs && python -m http.server # then open http://localhost:8000
```

> Open the page through a local server (as above), not by double-clicking the
> file — browsers block `fetch` of `jobs.json` from `file://`.

---

## Customizing

- **Rename the site / change the heading:** edit the `<h1>` and tagline near the
  top of `docs/index.html`.
- **Change how often it refreshes:** edit the `cron:` line in
  `.github/workflows/scrape.yml`.
- **TAMU full archive:** by default the TAMU scraper pulls the most recently
  posted jobs. To pull the entire board, open it in your browser, watch the
  Network tab while paging through results, and paste that request URL into
  `AJAX_URL` at the top of `sources/tamu.py`.
- **Adjust the FWS query:** edit `KEYWORD` / `ORG_MATCH` in
  `sources/usajobs_fws.py`.

## Adding another board later

Drop a new file in `sources/` that exposes `NAME`, `KEY`, and a `scrape()`
returning a list of dicts shaped like the others (`title, url, employer,
employer_type, location, salary, deadline, deadline_raw, published, tags,
detail_url, source, source_key`). Then add it to the `SOURCES` list in
`scrape.py`. Everything else — dedupe, sorting, the UI filters — picks it up
automatically.

## A note on what can and can't be aggregated

Big commercial boards (Indeed, LinkedIn, Glassdoor) block automated access and
have no open feed, so they're intentionally not here. This setup targets the
public-good niche boards that conservation roles actually get posted to.
