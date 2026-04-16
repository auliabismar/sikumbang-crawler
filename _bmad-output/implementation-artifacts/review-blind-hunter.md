# Review: Blind Hunter

You are a blind code reviewer. You receive ONLY the diff output below. No spec, no context docs, no project access.

## Instructions

Review the following diff for:
1. Security vulnerabilities
2. Logic errors
3. Resource leaks
4. Edge case failures

## Diff

```
diff --git a/requirements.txt b/requirements.txt
new file mode 100644
--- /dev/null
+++ b/requirements.txt
@@ -0,0 +1 @@
+playwright>=1.40.0

diff --git a/scraper/db.py b/scraper/db.py
new file mode 100644
--- /dev/null
+++ b/scraper/db.py
@@ -0,0 +1,83 @@
+import sqlite3
+import os
+from typing import Optional, List, Tuple
+
+DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'leads.db')
+
+def get_connection() -> sqlite3.Connection:
+    conn = sqlite3.connect(DB_PATH)
+    conn.row_factory = sqlite3.Row
+    return conn
+
+def init_db():
+    conn = get_connection()
+    cursor = conn.cursor()
+    cursor.execute('''
+        CREATE TABLE IF NOT EXISTS companies (
+            id INTEGER PRIMARY KEY AUTOINCREMENT,
+            name TEXT UNIQUE NOT NULL,
+            phone TEXT,
+            email TEXT,
+            website TEXT,
+            address TEXT,
+            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
+        )
+    ''')
+    cursor.execute('''
+        CREATE TABLE IF NOT EXISTS projects (
+            id INTEGER PRIMARY KEY AUTOINCREMENT,
+            company_id INTEGER NOT NULL,
+            project_name TEXT,
+            project_url TEXT NOT NULL,
+            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
+            FOREIGN KEY (company_id) REFERENCES companies(id)
+        )
+    ''')
+    conn.commit()
+    conn.close()
+
+def company_exists(company_name: str) -> bool:
+    conn = get_connection()
+    cursor = conn.cursor()
+    cursor.execute('SELECT id FROM companies WHERE name = ?', (company_name,))
+    result = cursor.fetchone()
+    conn.close()
+    return result is not None
+
+def add_company(name: str, phone: Optional[str] = None, email: Optional[str] = None,
+                website: Optional[str] = None, address: Optional[str] = None) -> int:
+    conn = get_connection()
+    cursor = conn.cursor()
+    try:
+        cursor.execute('''
+            INSERT INTO companies (name, phone, email, website, address)
+            VALUES (?, ?, ?, ?, ?)
+        ''', (name, phone, email, website, address))
+        company_id = cursor.lastrowid
+        conn.commit()
+        return company_id
+    except sqlite3.IntegrityError:
+        cursor.execute('SELECT id FROM companies WHERE name = ?', (name,))
+        result = cursor.fetchone()
+        conn.close()
+        return result['id'] if result else -1
+
+def add_project(company_id: int, project_name: Optional[str], project_url: str):
+    conn = get_connection()
+    cursor = conn.cursor()
+    cursor.execute('''
+        INSERT INTO projects (company_id, project_name, project_url)
+        VALUES (?, ?, ?, ?)
+    ''', (company_id, project_name, project_url)
+    conn.commit()
+    conn.close()
+
+def get_all_companies() -> List[Tuple]:
+    conn = get_connection()
+    cursor = conn.cursor()
+    cursor.execute('SELECT name, phone, email, website, address FROM companies')
+    rows = cursor.fetchall()
+    conn.close()
+    return rows
+
+def get_company_count() -> int:
+    conn = get_connection()
+    cursor = conn.cursor()
+    cursor.execute('SELECT COUNT(*) as count FROM companies')
+    result = cursor.fetchone()
+    conn.close()
+    return result['count'] if result else 0
+
+def get_project_count() -> int:
+    conn = get_connection()
+    cursor = conn.cursor()
+    cursor.execute('SELECT COUNT(*) as count FROM projects')
+    result = cursor.fetchone()
+    conn.close()
+    return result['count'] if result else 0
+
+if __name__ == '__main__':
+    init_db()
+    print(f"Database initialized at {DB_PATH}")

diff --git a/scraper/state.py b/scraper/state.py
new file mode 100644
--- /dev/null
+++ b/scraper/state.py
@@ -0,0 +1,63 @@
+import json
+import os
+from datetime import datetime
+from typing import Dict, List, Optional
+
+STATE_FILE = os.path.join(os.path.dirname(__file__), '..', 'state.json')
+
+def load_state() -> Dict:
+    if os.path.exists(STATE_FILE):
+        with open(STATE_FILE, 'r') as f:
+            return json.load(f)
+    return {
+        'last_successful_page': 0,
+        'processed_companies': [],
+        'failed_entries': [],
+        'timestamp': None
+    }
+
+def save_state(state: Dict) -> None:
+    state['timestamp'] = datetime.now().isoformat()
+    with open(STATE_FILE, 'w') as f:
+        json.dump(state, f, indent=2)
+
+def update_page_complete(page_num: int, company_names: List[str], failed: List[Dict] = None) -> None:
+    state = load_state()
+    state['last_successful_page'] = page_num
+    for name in company_names:
+        if name not in state['processed_companies']:
+            state['processed_companies'].append(name)
+    if failed:
+        for entry in failed:
+            existing = next((e for e in state['failed_entries'] if e['url'] == entry['url']), None)
+            if existing:
+                existing['retries'] = existing.get('retries', 0) + 1
+            else:
+                state['failed_entries'].append({**entry, 'retries': 1})
+    save_state(state)
+
+def add_failed_entry(url: str, error: str) -> None:
+    state = load_state()
+    existing = next((e for e in state['failed_entries'] if e['url'] == url), None)
+    if existing:
+        existing['retries'] = existing.get('retries', 0) + 1
+        if existing['retries'] >= 3:
+            return
+    else:
+        state['failed_entries'].append({'url': url, 'error': error, 'retries': 1})
+    save_state(state)
+
+def get_pending_failures(max_retries: int = 3) -> List[Dict]:
+    state = load_state()
+    return [e for e in state['failed_entries'] if e.get('retries', 0) < max_retries]
+
+def clear_failed_entries() -> None:
+    state = load_state()
+    state['failed_entries'] = []
+    save_state(state)
+
+def get_seen_companies() -> List[str]:
+    state = load_state()
+    return state.get('processed_companies', [])
+
+if __name__ == '__main__':
+    state = load_state()
+    print(f"Last page: {state['last_successful_page']}")
+    print(f"Companies processed: {len(state['processed_companies'])}")
+    print(f"Failed entries: {len(state['failed_entries'])}")

diff --git a/scraper/export.py b/scraper/export.py
new file mode 100644
--- /dev/null
+++ b/scraper/export.py
@@ -0,0 +1,22 @@
+import csv
+import os
+from scraper.db import get_all_companies
+
+OUTPUT_FILE = os.path.join(os.path.dirname(__file__), '..', 'leads_export.csv')
+
+def export_to_csv() -> str:
+    companies = get_all_companies()
+    with open(OUTPUT_FILE, 'w', newline='', encoding='utf-8') as f:
+        writer = csv.writer(f)
+        writer.writerow(['company_name', 'phone', 'email', 'website', 'address'])
+        for company in companies:
+            writer.writerow([
+                company['name'],
+                company['phone'] or '',
+                company['email'] or '',
+                company['website'] or '',
+                company['address'] or ''
+            ])
+    return OUTPUT_FILE
+
+if __name__ == '__main__':
+    output = export_to_csv()
+    print(f"Exported to {output}")

diff --git a/scraper/main.py b/scraper/main.py
new file mode 100644
--- /dev/null
+++ b/scraper/main.py
@@ -0,0 +1,121 @@
+import os
+import sys
+import time
+import re
+from playwright.sync_api import sync_playwright, Browser, Page, TimeoutError as PlaywrightTimeout
+
+sys.path.insert(0, os.path.dirname(__file__))
+from db import init_db, company_exists, add_company, add_project
+from state import load_state, save_state, update_page_complete, add_failed_entry, get_pending_failures, get_seen_companies
+from export import export_to_csv
+
+BASE_URL = 'https://sikumbang.tapera.go.id'
+TOTAL_PAGES = 1848
+DELAY_BETWEEN_PAGES = 8
+MAX_RETRIES = 3
+
+def check_robots_txt(browser: Browser) -> bool:
+    try:
+        page = browser.new_page()
+        robots_url = f'{BASE_URL}/robots.txt'
+        response = page.goto(robots_url, timeout=10000)
+        if response and response.status == 200:
+            content = page.content()
+            page.close()
+            if 'Disallow' in content:
+                print(f"[robots.txt] Found - checking directives...")
+                return True
+        page.close()
+        return True
+    except Exception as e:
+        print(f"[robots.txt] Could not check: {e}")
+        return True
+
+def parse_company_name(text: str) -> str:
+    match = re.match(r'^([^\(]+)', text.strip())
+    return match.group(1).strip() if match else text.strip()
+
+def extract_entries_from_page(page: Page) -> list:
+    entries = []
+    cards = page.locator('.card, [class*="card"]').all()
+    for card in cards:
+        try:
+            company_elem = card.locator('text=/\\(|company|name/i').first
+            if company_elem:
+                full_text = company_elem.inner_text()
+                company_name = parse_company_name(full_text)
+                detail_link = card.locator('text="Lihat detail lokasi"')
+                if detail_link.count() > 0:
+                    href = detail_link.get_attribute('href')
+                    if href:
+                        entries.append({
+                            'company_name': company_name,
+                            'detail_url': href if href.startswith('http') else BASE_URL + href
+                        })
+        except Exception:
+            continue
+    return entries
+
+def extract_detail_data(page: Page) -> dict:
+    data = {'phone': None, 'email': None, 'website': None, 'address': None}
+    try:
+        kantor_section = page.locator('text=/kantor pemasaran/i')
+        if kantor_section.count() > 0:
+            section = kantor_section.first
+            content = section.inner_text()
+            email_match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', content)
+            if email_match:
+                data['email'] = email_match.group()
+            phone_match = re.search(r'\+?[\d\s\-()]{8,}', content)
+            if phone_match:
+                data['phone'] = phone_match.group()
+            links = section.locator('a[href*="http"]').all()
+            for link in links:
+                href = link.get_attribute('href')
+                if href:
+                    if 'website' in link.inner_text().lower() or '.com' in href or '.id' in href:
+                        data['website'] = href
+                        break
+            address_text = content.split('Email')[0].split('Website')[0].split('Telepon')[1] if 'Telepon' in content else content
+            data['address'] = address_text.strip()
+    except Exception as e:
+        print(f"[detail] Error extracting data: {e}")
+    return data
+
+def process_entry(page: Page, entry: dict, seen_companies: set) -> bool:
+    company_name = entry['company_name']
+    if company_name in seen_companies:
+        return False
+    retry_count = 0
+    while retry_count < MAX_RETRIES:
+        try:
+            page.goto(entry['detail_url'], timeout=15000)
+            page.wait_for_load_state('networkidle', timeout=10000)
+            time.sleep(2)
+            detail_data = extract_detail_data(page)
+            company_id = add_company(
+                name=company_name,
+                phone=detail_data.get('phone'),
+                email=detail_data.get('email'),
+                website=detail_data.get('website'),
+                address=detail_data.get('address')
+            )
+            add_project(company_id, None, entry['detail_url'])
+            return True
+        except PlaywrightTimeout:
+            retry_count += 1
+            add_failed_entry(entry['detail_url'], 'timeout')
+        except Exception as e:
+            retry_count += 1
+            add_failed_entry(entry['detail_url'], str(e))
+            break
+    return False
+
+def run():
+    init_db()
+    state = load_state()
+    last_page = state.get('last_successful_page', 0)
+    seen_companies = set(get_seen_companies())
+    print(f"Starting from page {last_page + 1}")
+    print(f"Companies already processed: {len(seen_companies)}")
+    check_robots_txt(None)
+    with sync_playwright() as p:
+        browser = p.chromium.launch(headless=True)
+        page = browser.new_page()
+        page.set_default_timeout(30000)
+        failed_this_run = []
+        for page_num in range(last_page + 1, TOTAL_PAGES + 1):
+            print(f"Processing page {page_num}/{TOTAL_PAGES}")
+            retry_count = 0
+            while retry_count < MAX_RETRIES:
+                try:
+                    url = f'{BASE_URL}/page/{page_num}' if page_num > 1 else BASE_URL
+                    page.goto(url, timeout=20000)
+                    page.wait_for_load_state('networkidle', timeout=15000)
+                    time.sleep(3)
+                    entries = extract_entries_from_page(page)
+                    print(f"  Found {len(entries)} entries")
+                    processed_companies = []
+                    for entry in entries:
+                        if process_entry(page, entry, seen_companies):
+                            seen_companies.add(entry['company_name'])
+                            processed_companies.append(entry['company_name'])
+                    update_page_complete(page_num, processed_companies, failed_this_run)
+                    failed_this_run = []
+                    break
+                except PlaywrightTimeout:
+                    retry_count += 1
+                    print(f"  Timeout on page {page_num}, retry {retry_count}/{MAX_RETRIES}")
+                except Exception as e:
+                    retry_count += 1
+                    print(f"  Error on page {page_num}: {e}, retry {retry_count}/{MAX_RETRIES}")
+            if retry_count >= MAX_RETRIES:
+                print(f"  Skipping page {page_num} after {MAX_RETRIES} failures")
+            time.sleep(DELAY_BETWEEN_PAGES)
+        pending = get_pending_failures()
+        if pending:
+            print(f"Retrying {len(pending)} failed entries...")
+        browser.close()
+    print("Scraping complete!")
+    csv_path = export_to_csv()
+    print(f"Exported leads to {csv_path}")
+
+if __name__ == '__main__':
+    run()
```

## Output Format

Provide your review findings in this format:

**FINDINGS:**
1. [severity] - [file:line] - [description] - [recommendation]
2. ...

**SUMMARY:** Count of findings by severity (critical/high/medium/low)

---

Run your review in a separate session and paste back the findings.