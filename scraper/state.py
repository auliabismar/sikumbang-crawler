import json
import os
from datetime import datetime
from typing import Dict, List, Optional

STATE_FILE = os.path.join(os.path.dirname(__file__), "..", "state.json")


def load_state() -> Dict:
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    return {
        "last_successful_page": 0,
        "processed_companies": [],
        "failed_entries": [],
        "timestamp": None,
    }


def save_state(state: Dict) -> None:
    state["timestamp"] = datetime.now().isoformat()
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def update_page_complete(
    page_num: int, company_names: List[str], failed: List[Dict] = None
) -> None:
    state = load_state()
    state["last_successful_page"] = page_num
    for name in company_names:
        if name not in state["processed_companies"]:
            state["processed_companies"].append(name)
    if failed:
        for entry in failed:
            existing = next(
                (e for e in state["failed_entries"] if e["url"] == entry["url"]), None
            )
            if existing:
                existing["retries"] = existing.get("retries", 0) + 1
            else:
                state["failed_entries"].append({**entry, "retries": 1})
    save_state(state)


def add_failed_entry(url: str, error: str) -> None:
    state = load_state()
    existing = next((e for e in state["failed_entries"] if e["url"] == url), None)
    if existing:
        existing["retries"] = existing.get("retries", 0) + 1
        if existing["retries"] >= 3:
            return
    else:
        state["failed_entries"].append({"url": url, "error": error, "retries": 1})
    save_state(state)


def get_pending_failures(max_retries: int = 3) -> List[Dict]:
    state = load_state()
    return [e for e in state["failed_entries"] if e.get("retries", 0) < max_retries]


def clear_failed_entries() -> None:
    state = load_state()
    state["failed_entries"] = []
    save_state(state)


def get_seen_companies() -> List[str]:
    state = load_state()
    return state.get("processed_companies", [])


if __name__ == "__main__":
    state = load_state()
    print(f"Last page: {state['last_successful_page']}")
    print(f"Companies processed: {len(state['processed_companies'])}")
    print(f"Failed entries: {len(state['failed_entries'])}")
