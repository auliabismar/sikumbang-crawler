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
TOTAL_PAGES = 1848
DELAY_BETWEEN_PAGES = 8
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
    entries = []
    cards = page.locator('.card, [class*="card"]').all()
    for card in cards:
        try:
            company_elem = card.locator("text=/\\(|company|name/i").first
            if company_elem:
                full_text = company_elem.inner_text()
                company_name = parse_company_name(full_text)
                detail_link = card.locator('text="Lihat detail lokasi"')
                if detail_link.count() > 0:
                    href = detail_link.get_attribute("href")
                    if href:
                        entries.append(
                            {
                                "company_name": company_name,
                                "detail_url": href
                                if href.startswith("http")
                                else BASE_URL + href,
                            }
                        )
        except Exception:
            continue
    return entries


def extract_detail_data(page: Page) -> dict:
    data = {"phone": None, "email": None, "website": None, "address": None}
    try:
        kantor_section = page.locator("text=/kantor pemasaran/i")
        if kantor_section.count() > 0:
            section = kantor_section.first
            content = section.inner_text()
            email_match = re.search(r"[\w\.-]+@[\w\.-]+\.\w+", content)
            if email_match:
                data["email"] = email_match.group()
            phone_match = re.search(r"\+?[\d\s\-()]{8,}", content)
            if phone_match:
                data["phone"] = phone_match.group()
            links = section.locator('a[href*="http"]').all()
            for link in links:
                href = link.get_attribute("href")
                if href:
                    if (
                        "website" in link.inner_text().lower()
                        or ".com" in href
                        or ".id" in href
                    ):
                        data["website"] = href
                        break
            address_text = (
                content.split("Email")[0].split("Website")[0].split("Telepon")[1]
                if "Telepon" in content
                else content
            )
            data["address"] = address_text.strip()
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
            add_project(company_id, None, entry["detail_url"])
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
    check_robots_txt(None)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_default_timeout(30000)
        failed_this_run = []
        for page_num in range(last_page + 1, TOTAL_PAGES + 1):
            print(f"Processing page {page_num}/{TOTAL_PAGES}")
            retry_count = 0
            while retry_count < MAX_RETRIES:
                try:
                    url = f"{BASE_URL}/page/{page_num}" if page_num > 1 else BASE_URL
                    page.goto(url, timeout=20000)
                    page.wait_for_load_state("networkidle", timeout=15000)
                    time.sleep(3)
                    entries = extract_entries_from_page(page)
                    print(f"  Found {len(entries)} entries")
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
