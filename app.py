"""
Fake News Detector — Flask Backend
Searches a headline across 8 trusted news sources using Google News RSS
and direct source scraping as fallback. Uses rapidfuzz for headline matching.
"""

import time
import re
import urllib.parse
import requests
from bs4 import BeautifulSoup
from rapidfuzz import fuzz
from flask import Flask, request, jsonify
from flask_cors import CORS

import os

app = Flask(__name__, static_folder=os.path.dirname(os.path.abspath(__file__)), static_url_path="")
CORS(app, resources={r"/*": {"origins": "*"}}, supports_credentials=False)


@app.after_request
def add_cors_headers(response):
    """Ensure every response carries full CORS headers for mobile compatibility."""
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization, X-Requested-With"
    response.headers["Access-Control-Max-Age"] = "3600"
    return response

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)
HEADERS = {"User-Agent": USER_AGENT}
TIMEOUT = 10
MATCH_THRESHOLD = 70  # rapidfuzz score >= 70 means confirmed

TRUSTED_SOURCES = [
    {"name": "BBC",              "domain": "bbc.com",              "search_url": "https://www.bbc.co.uk/search?q={q}"},
    {"name": "Reuters",          "domain": "reuters.com",          "search_url": "https://www.reuters.com/site-search/?query={q}"},
    {"name": "Al Jazeera",       "domain": "aljazeera.com",        "search_url": "https://www.aljazeera.com/search/{q}"},
    {"name": "NDTV",             "domain": "ndtv.com",             "search_url": "https://www.ndtv.com/search?searchtext={q}"},
    {"name": "Times of India",   "domain": "timesofindia.indiatimes.com", "search_url": "https://timesofindia.indiatimes.com/topic/{q}"},
    {"name": "AP News",          "domain": "apnews.com",           "search_url": "https://apnews.com/search#{q}"},
    {"name": "The Hindu",        "domain": "thehindu.com",         "search_url": "https://www.thehindu.com/search/?q={q}"},
    {"name": "Hindustan Times",  "domain": "hindustantimes.com",   "search_url": "https://www.hindustantimes.com/search?q={q}"},
]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _extract_headline_from_url(url: str) -> str | None:
    """Fetch a URL and pull the main headline via og:title, <h1>, or <title>."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        # Try og:title first
        og = soup.find("meta", property="og:title")
        if og and og.get("content", "").strip():
            return og["content"].strip()

        # Then <h1>
        h1 = soup.find("h1")
        if h1 and h1.get_text(strip=True):
            return h1.get_text(strip=True)

        # Fallback to <title>
        if soup.title and soup.title.string:
            return soup.title.string.strip()
    except Exception:
        pass
    return None


def _best_match_score(headline: str, candidate_titles: list[str]) -> float:
    """Return the highest rapidfuzz ratio between headline and any candidate."""
    best = 0.0
    headline_lower = headline.lower().strip()
    for title in candidate_titles:
        title_lower = title.lower().strip()
        score = fuzz.ratio(headline_lower, title_lower)
        if score > best:
            best = score
        # Also try partial_ratio for substring matches
        partial = fuzz.partial_ratio(headline_lower, title_lower)
        if partial > best:
            best = partial
    return best


def _search_google_news_rss(headline: str, domain: str) -> list[str]:
    """
    Search Google News RSS feed restricted to a specific domain.
    Returns a list of article titles found.
    """
    query = f"{headline} site:{domain}"
    encoded = urllib.parse.quote(query)
    url = (
        f"https://news.google.com/rss/search?"
        f"q={encoded}&hl=en&gl=US&ceid=US:en"
    )
    titles = []
    try:
        resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, "xml")
            for item in soup.find_all("item"):
                tag = item.find("title")
                if tag and tag.text:
                    # Google News appends " - Source" to titles; strip it
                    raw = tag.text.strip()
                    cleaned = re.sub(r"\s*-\s*[^-]+$", "", raw).strip()
                    titles.append(cleaned)
    except Exception:
        pass
    return titles


def _scrape_source_search(headline: str, search_url_template: str) -> list[str]:
    """
    Fallback: hit the source's own search page and pull candidate headline strings.
    """
    q = urllib.parse.quote_plus(headline)
    url = search_url_template.replace("{q}", q)
    titles = []
    try:
        resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, "html.parser")
            # Grab text from heading tags and anchors likely to be article titles
            for tag in soup.find_all(["h1", "h2", "h3", "h4", "a"]):
                text = tag.get_text(strip=True).replace("\n", " ")
                # Filter to reasonable headline lengths
                if 15 <= len(text) <= 200:
                    titles.append(text)
            # De-duplicate while preserving order
            seen = set()
            unique = []
            for t in titles:
                if t not in seen:
                    seen.add(t)
                    unique.append(t)
            titles = unique
    except Exception:
        pass
    return titles


def _check_source(headline: str, source: dict) -> dict:
    """
    Check a single source for the headline.
    Returns a dict with source info, match status, and best score.
    """
    result = {
        "name": source["name"],
        "domain": source["domain"],
        "matched": False,
        "best_score": 0.0,
        "method": None,
    }

    # ---- Primary: Google News RSS with site: filter ----
    rss_titles = _search_google_news_rss(headline, source["domain"])
    if rss_titles:
        score = _best_match_score(headline, rss_titles)
        result["best_score"] = score
        if score >= MATCH_THRESHOLD:
            result["matched"] = True
            result["method"] = "google_news_rss"
            return result

    time.sleep(0.5)

    # ---- Fallback: Direct source scraping ----
    scraped_titles = _scrape_source_search(headline, source["search_url"])
    if scraped_titles:
        score = _best_match_score(headline, scraped_titles)
        if score > result["best_score"]:
            result["best_score"] = score
        if score >= MATCH_THRESHOLD:
            result["matched"] = True
            result["method"] = "direct_scrape"

    return result


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route("/analyze", methods=["GET", "POST", "OPTIONS"])
def analyze():
    # Handle CORS preflight
    if request.method == "OPTIONS":
        return "", 204

    # Support both GET (?input=...) and POST ({"input": ...}) for compatibility
    if request.method == "GET":
        raw_input = (request.args.get("input") or "").strip()
        data = {"input": raw_input}
    else:
        data = request.get_json(force=True)
    raw_input = (data.get("input") or "").strip()

    if not raw_input:
        return jsonify({"error": "No input provided"}), 400

    # Determine if input is a URL → scrape headline
    headline = raw_input
    is_url = raw_input.startswith("http://") or raw_input.startswith("https://")
    if is_url:
        extracted = _extract_headline_from_url(raw_input)
        if not extracted:
            return jsonify({"error": "Could not extract headline from URL"}), 422
        headline = extracted

    # Search across all trusted sources
    matched_sources = []
    searched_sources = []

    for source in TRUSTED_SOURCES:
        result = _check_source(headline, source)
        searched_sources.append({
            "name": result["name"],
            "domain": result["domain"],
            "matched": result["matched"],
            "score": round(result["best_score"], 1),
            "method": result["method"],
        })
        if result["matched"]:
            matched_sources.append(result["name"])
        time.sleep(0.5)

    # Verdict
    confirmed = len(matched_sources)
    total = len(TRUSTED_SOURCES)
    probability = round((confirmed / total) * 100, 1) if total else 0

    if confirmed >= 3:
        verdict = "REAL"
    elif confirmed >= 1:
        verdict = "POSSIBLY REAL"
    else:
        verdict = "LIKELY FAKE"

    return jsonify({
        "verdict": verdict,
        "probability": probability,
        "matched_sources": matched_sources,
        "searched_sources": searched_sources,
        "headline_used": headline,
    })


@app.route("/", methods=["GET"])
def index():
    """Serve the frontend HTML."""
    return app.send_static_file("index.html")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
