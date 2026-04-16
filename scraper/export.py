import csv
import os
from scraper.db import get_all_companies

OUTPUT_FILE = os.path.join(os.path.dirname(__file__), "..", "leads_export.csv")


def export_to_csv() -> str:
    companies = get_all_companies()
    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["company_name", "phone", "email", "website", "address"])
        for company in companies:
            writer.writerow(
                [
                    company["name"],
                    company["phone"] or "",
                    company["email"] or "",
                    company["website"] or "",
                    company["address"] or "",
                ]
            )
    return OUTPUT_FILE


if __name__ == "__main__":
    output = export_to_csv()
    print(f"Exported to {output}")
