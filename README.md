# Sikumbang Tapera Scraper

Web scraper for Indonesian real estate company registry at [sikumbang.tapera.go.id](https://sikumbang.tapera.go.id).

## Purpose

Collect company lead data (name, phone, email, website, address) for outreach campaigns from the Tapera government registry.

## Features

- **Polite scraping** with 8-second delays to avoid IP bans
- **Resume capability** - interrupted runs resume from last successful page
- **Company deduplication** - Indonesian company names are unique keys; each company scraped only once
- **SQLite storage** - tracks all companies and projects
- **CSV export** - ready for Apollo.io or other outreach tools

## Architecture

- `scraper/main.py` - Playwright orchestrator (page iteration, entry extraction, detail clicking)
- `scraper/db.py` - SQLite operations (company/project storage, dedup logic)
- `scraper/state.py` - JSON state file (last_successful_page, processed_companies, failed_entries)
- `scraper/export.py` - CSV export for lead lists

## Setup

```bash
pip install -r requirements.txt
python -m playwright install chromium
```

## Usage

```bash
# Run scraper (will resume from last position if interrupted)
python scraper/main.py

# Export to CSV
python scraper/export.py
```

## Data Flow

1. Scan listing pages (1848 pages × 18 entries)
2. Extract company name from each card (text before `(`)
3. If company NOT in seen_companies → click detail page → extract (phone, email, website, address)
4. If company IS in seen_companies → skip (already have data)
5. Save state after each page
6. On interruption → resume from last_successful_page + 1

## Output Files

| File | Description |
|------|-------------|
| `leads.db` | SQLite database (created at runtime) |
| `state.json` | Resume state file (created at runtime) |
| `leads_export.csv` | Exported lead list (created on demand) |

## Constraints

- **Always** respect robots.txt
- **Always** 8-second delay between page requests
- **Max** 3 retries per entry before skipping
- **Never** re-scrape a company once data is captured