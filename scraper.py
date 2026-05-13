"""Yahoo!ファイナンス掲示板のアレムさんの投稿を監視してTelegramに通知する。"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

import requests
from bs4 import BeautifulSoup

USER_ID = os.environ.get("YAHOO_USER_ID", "")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

TARGET_URL = f"https://finance.yahoo.co.jp/cm/personal/history/comment?user={USER_ID}"
STATE_FILE = Path(__file__).parent / "state.json"

DATE_RE = re.compile(r"\d{4}/\d{1,2}/\d{1,2}\s+\d{1,2}:\d{2}")
COMMENT_NO_RE = re.compile(r"No\.(\d+)")
MESSAGE_PATH_RE = re.compile(r"/cm/message/(\d+)/([0-9a-f]+)(?:/(\d+))?")


def fetch_page() -> str:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
        ),
        "Accept-Language": "ja,en;q=0.8",
    }
    r = requests.get(TARGET_URL, headers=headers, timeout=30)
    r.raise_for_status()
    return r.text


def parse_comments(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "lxml")
    results: list[dict] = []
    seen_keys: set[str] = set()

    for li in soup.find_all("li"):
        text = li.get_text(" ", strip=True)
        if not text:
            continue
        date_match = DATE_RE.search(text)
        no_match = COMMENT_NO_RE.search(text)
        if not (date_match and no_match):
            continue

        thread_link = None
        comment_link = None
        for a in li.find_all("a", href=True):
            href = a["href"]
            m = MESSAGE_PATH_RE.search(href)
            if not m:
                continue
            if m.group(3):
                comment_link = (a.get_text(strip=True), href)
            else:
                thread_link = (a.get_text(strip=True), href)

        if not thread_link:
            continue

        thread_name, thread_href = thread_link
        comment_no = no_match.group(1)
        date_str = date_match.group(0)

        key = f"{thread_href}#{comment_no}"
        if key in seen_keys:
            continue
        seen_keys.add(key)

        body = text
        body = DATE_RE.sub("", body)
        body = COMMENT_NO_RE.sub("", body)
        if thread_name:
            body = body.replace(thread_name, "", 1)
        body = body.strip(" 　-:|・")

        if comment_link:
            permalink = comment_link[1]
        else:
            permalink = thread_href.rstrip("/") + f"/{comment_no}"
        if permalink.startswith("/"):
            permalink = "https://finance.yahoo.co.jp" + permalink

        results.append(
            {
                "id": key,
                "thread": thread_name,
                "thread_url": (
                    "https://finance.yahoo.co.jp" + thread_href
                    if thread_href.startswith("/")
                    else thread_href
                ),
                "no": comment_no,
                "date": date_str,
                "body": body,
                "url": permalink,
            }
        )

    return results


def load_state() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    return {"seen_ids": [], "initialized": False}


def save_state(state: dict) -> None:
    STATE_FILE.write_text(
        json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def send_telegram(text: str) -> None:
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": False,
    }
    r = requests.post(url, json=payload, timeout=30)
    r.raise_for_status()


def html_escape(s: str) -> str:
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def format_message(c: dict) -> str:
    body = html_escape(c["body"])
    if len(body) > 600:
        body = body[:600] + "…"
    return (
        f"🔔 <b>アレムさんが投稿</b>\n"
        f"📋 <b>{html_escape(c['thread'])}</b>  No.{c['no']}\n"
        f"🕒 {html_escape(c['date'])}\n\n"
        f"{body}\n\n"
        f'<a href="{html_escape(c["url"])}">投稿を開く</a>'
    )


def main() -> int:
    if not (USER_ID and TELEGRAM_TOKEN and TELEGRAM_CHAT_ID):
        print("ERROR: Missing env vars (YAHOO_USER_ID / TELEGRAM_TOKEN / TELEGRAM_CHAT_ID)")
        return 2

    html = fetch_page()
    comments = parse_comments(html)
    print(f"Fetched {len(comments)} comments from page.")

    if not comments:
        print("WARNING: parser returned 0 comments. HTML structure may have changed.")
        return 0

    state = load_state()
    seen: set[str] = set(state.get("seen_ids", []))
    initialized: bool = state.get("initialized", False)

    new_comments = [c for c in comments if c["id"] not in seen]
    new_comments.sort(key=lambda c: c["date"])
    print(f"New comments: {len(new_comments)}")

    if initialized:
        for c in new_comments:
            try:
                send_telegram(format_message(c))
                print(f"Notified: {c['thread']} No.{c['no']}")
            except Exception as e:
                print(f"Telegram send failed: {e}")
                return 1
    else:
        print("First run: seeding state without sending notifications.")

    all_ids = list(seen) + [c["id"] for c in new_comments]
    state["seen_ids"] = all_ids[-300:]
    state["initialized"] = True
    save_state(state)
    return 0


if __name__ == "__main__":
    sys.exit(main())
