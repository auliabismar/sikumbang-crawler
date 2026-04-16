---
title: 'sikumbang-tapera-scraper'
type: 'feature'
created: '2026-04-16'
status: 'done'
context: []
---

## Intent

**Problem:** Need to collect Indonesian real estate company lead data (name, phone, email, website) from sikumbang.tapera.go.id government registry for outreach campaigns. Site has ~1848 paginated pages with 18 entries each (~33K total entries), but Indonesian company names are unique business registrations allowing major deduplication.

**Approach:** Polite web scraper using Playwright (browser automation required - site loads data via JavaScript). SQLite tracks seen companies for deduplication; CSV exports lead list for Apollo.io. Resume-capable via JSON state file.

## Boundaries & Constraints

**Always:**
- Respect robots.txt
- 8-second delay between page requests (IP ban prevention)
- Company name is unique key in Indonesia (deduplication via seen_companies set)
- Only click detail page if company NOT in seen_companies
- Save state after each page (resume capability)
- Maximum 3 retries per entry before skipping

**Ask First:** N/A

**Never:**
- Aggressive scraping (risk IP ban)
- Re-scrape company after data captured
- Skip robots.txt check

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| LISTING_PAGE | Page URL (e.g., page/847) | Extract 18 entries (company_name, project_url) | Log error, skip after 3 retries |
| DETAIL_PAGE_CLICK | company_name not in seen_companies | Click "Lihat detail lokasi", extract (phone, email, website, address) | Log error, skip after 3 retries |
| DETAIL_PAGE_SKIP | company_name in seen_companies | Skip click, do not re-scrape | N/A |
| COMPANY_NAME_PARSE | Card text: "PT Contoh (APARTemen)" | company_name = "PT Contoh" (text before parenthesis) | Ignore association in parentheses |
| INTERRUPTION | Any state | On restart, resume from last_successful_page + 1 | N/A |
| COMPLETION | All pages processed | Attempt failed entries (max 3 retries each), then finalize | N/A |

## Code Map

- `scraper/main.py` -- Playwright scraper orchestrator (page iteration, entry extraction, detail clicking)
- `scraper/db.py` -- SQLite operations (company/project storage, seen_companies tracking)
- `scraper/state.py` -- JSON state file (last_successful_page, last_position, failed_entries)
- `scraper/export.py` -- CSV export for Apollo.io
- `requirements.txt` -- Python dependencies (playwright, sqlite3)
- `state.json` -- Resume state file (created at runtime)
- `leads.db` -- SQLite database (created at runtime)
- `leads_export.csv` -- Exported lead list (created on demand)

## Tasks & Acceptance

**Execution:**
- [x] `requirements.txt` -- Define dependencies (playwright>=1.40, sqlite3 built-in)
- [x] `scraper/db.py` -- Create SQLite schema (companies, projects tables), implement dedup logic
- [x] `scraper/state.py` -- JSON read/write for resume state, checkpoint after each page
- [x] `scraper/export.py` -- CSV export with columns: company_name, phone, email, website, address, project_url
- [x] `scraper/main.py` -- Playwright browser setup, page iteration, company_name parsing (strip association), detail page click logic, 8-second delay, robots.txt check

**Acceptance Criteria:**
- Given listing page with 18 entries, when company_name extracted, then association in parentheses is stripped
- Given company NOT in seen_companies, when detail page visited, then data (phone/email/website/address) captured
- Given company IS in seen_companies, when listing page processed, then detail page NOT clicked
- Given interruption during scraping, when scraper restarts, then resume from last_successful_page + 1
- Given completed run, when export triggered, then leads_export.csv contains all unique companies with complete contact data

## Design Notes

**Company Name Parsing:**
- Card text format: "PT Contoh (ASSOCIATION_NAME)"
- Extract company_name = text BEFORE first `(` character
- Ignore association name entirely

**Dual-Layer Deduplication:**
1. URL tracking (project_url in seen_urls set) = which project pages visited
2. Company name check (before clicking detail) = only visit detail page for new companies

**State Structure:**
```json
{
  "last_successful_page": 847,
  "processed_companies": ["PT ABC", "PT XYZ"],
  "failed_entries": [{"url": "...", "error": "timeout", "retries": 3}],
  "timestamp": "2026-04-16T14:30:00"
}
```

**Polite Scraping Flow:**
```
for page in range(1, 1849):
    load page
    for entry in entries:
        company_name = extract(entry)
        if company_name not in seen_companies:
            click detail page
            extract data
            add to db
    save state
    sleep 8 seconds
```

## Verification

**Commands:**
- `python -m playwright install chromium` -- expected: chromium installed successfully
- `python scraper/main.py` -- expected: starts scraping from page 1 (or resume point)
- `python scraper/export.py` -- expected: leads_export.csv created with company data

**Manual checks (if no CLI):**
- Open leads.db in DB Browser for SQLite, verify companies table has data
- Check state.json has last_successful_page updated after each page
- Open CSV in spreadsheet, verify columns: company_name, phone, email, website, address

## Suggested Review Order

**Entry Point (Orchestration)**

- Playwright browser setup, page iteration, polite delay, entry processing flow
  [`scraper/main.py`](../../scraper/main.py#L1)

**Data Layer (Storage & Export)**

- SQLite schema and company/project dedup logic
  [`scraper/db.py`](../../scraper/db.py#L1)
- CSV export for Apollo.io lead list
  [`scraper/export.py`](../../scraper/export.py#L1)

**State Management (Resume Capability)**

- JSON state file for last_page, processed_companies, failed_entries tracking
  [`scraper/state.py`](../../scraper/state.py#L1)

**Configuration**

- Python dependency for Playwright browser automation
  [`requirements.txt`](../../requirements.txt#L1)