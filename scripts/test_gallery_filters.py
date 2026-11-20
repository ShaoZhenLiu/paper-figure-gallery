#!/usr/bin/env python3
"""Check that the curated option only filters results in a real browser."""

import argparse
import json
from contextlib import contextmanager
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from urllib.parse import urlencode

from playwright.sync_api import sync_playwright

from gallery_extension.arxiv import installed_browser
from gallery_extension.catalog import ROOT


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, format, *args):
        pass


@contextmanager
def local_gallery():
    handler = partial(QuietHandler, directory=str(ROOT))
    with ThreadingHTTPServer(("127.0.0.1", 0), handler) as server:
        worker = Thread(target=server.serve_forever, daemon=True)
        worker.start()
        try:
            yield f"http://127.0.0.1:{server.server_port}/"
        finally:
            server.shutdown()
            worker.join()


def filter_state(page):
    return page.evaluate("""() => ({
        totals: document.querySelector('#hero-stats').textContent,
        years: document.querySelector('.gallery-years').textContent,
        chips: Array.from(document.querySelectorAll('.chips'), box => box.innerHTML),
        search: document.querySelector('#search').value,
        sort: document.querySelector('#sort').value,
    })""")


def result_count(page):
    return tuple(int(text.replace(",", "")) for text in
                 page.locator("#result-count").inner_text().split() if text.replace(",", "").isdigit())


def verify(url, expected):
    options = {"headless": True}
    if installed_browser():
        options["executable_path"] = str(installed_browser())
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(**options)
        page = browser.new_page(locale="zh-CN", viewport={"width": 1450, "height": 990})
        page.goto(url, wait_until="domcontentloaded")
        page.locator("#result-count b").wait_for()
        curated, added, article = page.evaluate("""() => [
            window.FIGURES.length, window.GALLERY_ADDITIONS.length,
            window.GALLERY_ADDITIONS.find(figure => figure.venue === 'tmlr' && figure.award)
        ]""")
        assert article
        total = curated + added
        assert expected is None or total == expected, total
        assert result_count(page) == (curated, total)
        curated_button = page.locator("#curated-only")
        assert curated_button.get_attribute("aria-pressed") == "true"
        baseline = filter_state(page)
        assert "2017–2026" in baseline["years"]
        assert page.locator("#year-chips [data-val='2017']").count() == 1
        assert page.locator("#venue-chips [data-val='tmlr']").count() == 1

        curated_button.click()
        assert result_count(page) == (total, total)
        assert curated_button.get_attribute("aria-pressed") == "false"
        assert filter_state(page) == baseline
        assert page.locator(".forge-cta, .forge-nav, #gallery-domain-notice, script[src*='analytics']").count() == 0

        params = {"v": "tmlr", "y": article["year"], "t": "best", "p": article["pattern"],
                  "s": "title", "q": article["title"]}
        page.goto(url + "?" + urlencode(params), wait_until="domcontentloaded")
        page.locator("#result-count b").wait_for()
        selected = filter_state(page)
        assert result_count(page) == (0, total)
        curated_button.click()
        assert result_count(page) == (1, total)
        assert filter_state(page) == selected
        card = page.locator(f'[data-id="{article["id"]}"]')
        assert card.is_visible()
        curated_button.click()
        assert result_count(page) == (0, total)
        assert filter_state(page) == selected

        page.goto(url + "#f=" + article["id"], wait_until="domcontentloaded")
        page.locator("#lightbox").wait_for(state="visible")
        assert page.locator("#lb-title").text_content() == article["title"]
        page.wait_for_function("w => document.querySelector('#lb-img').naturalWidth === w",
                               arg=article["w"], timeout=30000)
        assert curated_button.get_attribute("aria-pressed") == "false"
        assert not page.evaluate("Boolean(window.__tcLastError)")
        print(json.dumps({"curated": curated, "total": total, "sample": article["id"]}))
        browser.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", help="Test a deployed gallery instead of a local one")
    parser.add_argument("--total", type=int, help="Expected global figure count")
    args = parser.parse_args()
    if args.url:
        verify(args.url.rstrip("/") + "/", args.total)
    else:
        with local_gallery() as url:
            verify(url, args.total)


if __name__ == "__main__":
    main()
