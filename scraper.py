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

COMMENT_NO_RE = re.compile(r"No\.(\d+)")
BASE_URL = "https://finance.yahoo.co.jp"


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


def _abs_url(href: str) -> str:
    if href.startswith("/"):
        return BASE_URL + href
    return href


def parse_comments(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "lxml")
    results: list[dict] = []
    seen_keys: set[str] = set()

    for box in soup.select("li.commentBox"):
        thread_a = box.select_one(".breadcrumbs a")
        cn_el = box.select_one(".commentNumber")
        date_p = box.select_one(".ttlInfoDateNum p")
        if not (thread_a and cn_el and date_p):
            continue

        no_match = COMMENT_NO_RE.search(cn_el.get_text())
        if not no_match:
            continue

        thread_name = thread_a.get_text(strip=True)
        thread_href = thread_a.get("href", "")
        comment_no = no_match.group(1)
        date_str = date_p.get_text(strip=True)

        key = f"{thread_href}#{comment_no}"
        if key in seen_keys:
            continue
        seen_keys.add(key)

        detail = box.select_one(".detail")
        body = detail.get_text(" ", strip=True) if detail else ""
        if not body:
            title_a = box.select_one(".commentTitleArea a")
            if title_a:
                body = title_a.get_text(strip=True)

        title_a = box.select_one(".commentTitleArea a")
        if title_a and title_a.get("href"):
            permalink = _abs_url(title_a["href"])
        else:
            permalink = _abs_url(thread_href.rstrip("/") + f"/{comment_no}")

        results.append(
            {
                "id": key,
                "thread": thread_name,
                "thread_url": _abs_url(thread_href),
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
        latest = new_comments[-1] if new_comments else None
        latest_info = (
            f"📋 直近の投稿: {latest['thread']} No.{latest['no']} ({latest['date']})"
            if latest
            else "📋 直近の投稿: なし"
        )
        try:
            send_telegram(
                "✅ <b>アレム通知Bot 稼働開始</b>\n"
                f"監視中のコメント数: {len(comments)}件\n"
                f"{latest_info}\n\n"
                "次回以降、新着投稿があったらこのチャットに通知します🔔"
            )
            print("Sent initialization message.")
        except Exception as e:
            print(f"Init message send failed: {e}")
            return 1

    all_ids = list(seen) + [c["id"] for c in new_comments]
    state["seen_ids"] = all_ids[-300:]
    state["initialized"] = True
    save_state(state)
    return 0


if __name__ == "__main__":
    sys.exit(main())
