import os
import sys
import time
import re
from playwright.sync_api import (
    sync_playwright,
    Browser,
    Page,
    TimeoutError as PlaywrightTimeout,
)

sys.path.insert(0, os.path.dirname(__file__))
from db import init_db, company_exists, add_company, add_project
from state import (
    load_state,
    save_state,
    update_page_complete,
    add_failed_entry,
    get_pending_failures,
    get_seen_companies,
)
from export import export_to_csv

BASE_URL = "https://sikumbang.tapera.go.id"
TOTAL_PAGES = 50

DELAY_BETWEEN_PAGES = 2
MAX_RETRIES = 3


def check_robots_txt(browser: Browser) -> bool:
    try:
        page = browser.new_page()
        robots_url = f"{BASE_URL}/robots.txt"
        response = page.goto(robots_url, timeout=10000)
        if response and response.status == 200:
            content = page.content()
            page.close()
            if "Disallow" in content:
                print(f"[robots.txt] Found - checking directives...")
                return True
        page.close()
        return True
    except Exception as e:
        print(f"[robots.txt] Could not check: {e}")
        return True


def parse_company_name(text: str) -> str:
    match = re.match(r"^([^\(]+)", text.strip())
    return match.group(1).strip() if match else text.strip()


def extract_entries_from_page(page: Page) -> list:
    entries = page.evaluate("""
() => {
    const entries = [];
    const cards = document.querySelectorAll('.col-md-6.col-lg-4.col-sm-12.my-4');
    cards.forEach(card => {
        const h5 = card.querySelector('h5');
        if (!h5) return;

        const projectName = h5.textContent.trim();

        const col12 = card.querySelector('.col-md-12');
        if (!col12) return;

        const spans = col12.querySelectorAll('span');
        let companyName = '';
        spans.forEach(span => {
            const text = span.textContent.trim();
            if (text && text.includes('(')) {
                companyName = text.replace(/\\s*\\([^)]*\\)\\s*$/, '').trim();
            }
        });

        const link = card.querySelector('a[href*="lokasi-perumahan"]');
        if (!link) return;

        entries.push({
            project_name: projectName,
            company_name: companyName,
            detail_url: link.href
        });
    });
    return entries;
}
""")
    print(f"Found {len(entries)} entries")
    return entries


def extract_detail_data(page: Page) -> dict:
    data = {"phone": None, "email": None, "website": None, "address": None}
    try:
        kantor_heading = page.locator(
            "h4:has-text('Kantor Pemasaran'), h5:has-text('Kantor Pemasaran')"
        )
        if kantor_heading.count() > 0:
            heading = kantor_heading.first
            parent = heading.locator("..").first
            data_container = parent.locator("..").first

            paragraphs = data_container.locator("p").all()
            for p in paragraphs:
                text = p.inner_text()
                if "Telp" in text:
                    match = re.search(r"[\d\s\-()]{8,}", text)
                    if match:
                        data["phone"] = match.group().strip()
                elif "Email" in text:
                    match = re.search(r"[\w\.-]+@[\w\.-]+\.\w+", text)
                    if match:
                        data["email"] = match.group()
                elif "Website" in text:
                    link = p.locator("a").first
                    if link.count() > 0:
                        href = link.get_attribute("href")
                        if href and href != "http://":
                            data["website"] = href
                else:
                    if text.strip() and not data["address"]:
                        data["address"] = text.strip()
    except Exception as e:
        print(f"[detail] Error extracting data: {e}")
    return data


def process_entry(page: Page, entry: dict, seen_companies: set) -> bool:
    company_name = entry["company_name"]
    if company_name in seen_companies:
        return False
    retry_count = 0
    while retry_count < MAX_RETRIES:
        try:
            page.goto(entry["detail_url"], timeout=15000)
            page.wait_for_load_state("networkidle", timeout=10000)
            time.sleep(2)
            detail_data = extract_detail_data(page)
            company_id = add_company(
                name=company_name,
                phone=detail_data.get("phone"),
                email=detail_data.get("email"),
                website=detail_data.get("website"),
                address=detail_data.get("address"),
            )
            add_project(company_id, entry.get("project_name"), entry["detail_url"])
            return True
        except PlaywrightTimeout:
            retry_count += 1
            add_failed_entry(entry["detail_url"], "timeout")
        except Exception as e:
            retry_count += 1
            add_failed_entry(entry["detail_url"], str(e))
            break
    return False


def run():
    init_db()
    state = load_state()
    last_page = state.get("last_successful_page", 0)
    seen_companies = set(get_seen_companies())
    print(f"Starting from page {last_page + 1}")
    print(f"Companies already processed: {len(seen_companies)}")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        check_robots_txt(browser)
        page = browser.new_page()
        page.set_default_timeout(30000)
        failed_this_run = []
        page.goto(BASE_URL, timeout=30000)
        page.wait_for_load_state("networkidle", timeout=20000)
        page.wait_for_selector(".container", timeout=10000)
        time.sleep(2)
        for page_num in range(last_page + 1, TOTAL_PAGES + 1):
            print(f"Processing page {page_num}/{TOTAL_PAGES}")
            retry_count = 0
            while retry_count < MAX_RETRIES:
                try:
                    if page_num > 1:
                        page.goto(f"{BASE_URL}/?page={page_num}", timeout=30000)
                        page.wait_for_load_state("networkidle", timeout=30000)
                        page.wait_for_selector(
                            ".col-md-6.col-lg-4.col-sm-12.my-4", timeout=15000
                        )
                        time.sleep(2)
                    entries = extract_entries_from_page(page)
                    print(f"  Found {len(entries)} entries")
                    for i, entry in enumerate(entries):
                        print(
                            f"  Processing entry {i + 1}/{len(entries)}: {entry['company_name']}"
                        )
                    processed_companies = []
                    for entry in entries:
                        if process_entry(page, entry, seen_companies):
                            seen_companies.add(entry["company_name"])
                            processed_companies.append(entry["company_name"])
                    update_page_complete(page_num, processed_companies, failed_this_run)
                    failed_this_run = []
                    break
                except PlaywrightTimeout:
                    retry_count += 1
                    print(
                        f"  Timeout on page {page_num}, retry {retry_count}/{MAX_RETRIES}"
                    )
                except Exception as e:
                    retry_count += 1
                    print(
                        f"  Error on page {page_num}: {e}, retry {retry_count}/{MAX_RETRIES}"
                    )
            if retry_count >= MAX_RETRIES:
                print(f"  Skipping page {page_num} after {MAX_RETRIES} failures")
            time.sleep(DELAY_BETWEEN_PAGES)
        pending = get_pending_failures()
        if pending:
            print(f"Retrying {len(pending)} failed entries...")
        browser.close()
    print("Scraping complete!")
    csv_path = export_to_csv()
    print(f"Exported leads to {csv_path}")


if __name__ == "__main__":
    run()
