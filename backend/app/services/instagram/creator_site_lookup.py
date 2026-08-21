from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Awaitable, Callable, Iterable, Optional
from urllib.parse import parse_qs, quote, urljoin, urlsplit, urlunsplit

from bs4 import BeautifulSoup

from ..blog.extractor import parse_recipes_from_html
from ..extraction_types import ExtractionResult
from ..public_web import HTML_POLICY, PublicWebError, safe_fetch


MAX_RANKED_PROFILE_LINKS = 3
MAX_CREATOR_SITE_DOMAINS = 2
MAX_CANDIDATE_PAGES = 5

SOCIAL_STOREFRONT_HOSTS = frozenset(
    {
        "instagram.com",
        "facebook.com",
        "fb.com",
        "twitter.com",
        "x.com",
        "tiktok.com",
        "youtube.com",
        "youtu.be",
        "pinterest.com",
        "threads.net",
        "snapchat.com",
        "whatsapp.com",
        "linkedin.com",
        "amazon.com",
        "etsy.com",
        "shop.app",
        "venmo.com",
        "cash.app",
        "patreon.com",
        "onlyfans.com",
    }
)

LINK_HUB_HOSTS = frozenset(
    {
        "linktr.ee",
        "bio.site",
        "beacons.ai",
        "linkin.bio",
        "campsite.bio",
        "msha.ke",
        "tap.bio",
        "shorby.com",
        "koji.to",
        "lnk.bio",
        "buzzfeed.bio",
    }
)

_FOOD_SIGNAL_RE = re.compile(
    r"recipe|recipes|food|cook|kitchen|eats|bakes|bakery|chef|culinary|dish|meal",
    re.IGNORECASE,
)

_GENERIC_TITLE_TOKENS = frozenset(
    {
        "recipe",
        "recipes",
        "easy",
        "quick",
        "best",
        "homemade",
        "classic",
        "the",
        "a",
        "an",
        "simple",
        "delicious",
        "perfect",
        "healthy",
    }
)

_TIME_QUALIFIER_UNITS = frozenset(
    {
        "minute",
        "minutes",
        "min",
        "mins",
        "hour",
        "hours",
        "hr",
        "hrs",
        "second",
        "seconds",
        "ingredient",
        "ingredients",
    }
)

TAXONOMY_PATH_MARKERS = ("/category/", "/tag/", "/author/", "/page/")

_PUNCT_RE = re.compile(r"[^\w\s]", re.UNICODE)


def _hostname(url: str) -> Optional[str]:
    try:
        return urlsplit(url).hostname
    except ValueError:
        return None


def _host_matches(hostname: Optional[str], hosts: frozenset[str]) -> bool:
    if not hostname:
        return False
    folded = hostname.casefold()
    return any(folded == host or folded.endswith(f".{host}") for host in hosts)


def is_social_or_storefront(url: str) -> bool:
    return _host_matches(_hostname(url), SOCIAL_STOREFRONT_HOSTS)


def is_link_hub(url: str) -> bool:
    return _host_matches(_hostname(url), LINK_HUB_HOSTS)


def unwrap_instagram_redirect(url: str) -> str:
    hostname = _hostname(url)
    if hostname is None or hostname.casefold() != "l.instagram.com":
        return url
    query = parse_qs(urlsplit(url).query)
    targets = query.get("u")
    if not targets:
        return url
    target = targets[0]
    parsed = urlsplit(target)
    if parsed.scheme.casefold() != "https" or not parsed.hostname:
        return url
    return target


def normalize_profile_links(raw_links: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    normalized: list[str] = []
    for raw in raw_links:
        if not isinstance(raw, str):
            continue
        candidate = raw.strip()
        if not candidate:
            continue
        try:
            parsed = urlsplit(candidate)
            port = parsed.port
        except (TypeError, ValueError):
            continue
        if parsed.scheme.casefold() != "https" or not parsed.hostname:
            continue
        host = parsed.hostname.casefold()
        if port is not None and port != 443:
            host = f"{host}:{port}"
        cleaned = urlunsplit(("https", host, parsed.path or "/", parsed.query, ""))
        if cleaned in seen:
            continue
        seen.add(cleaned)
        normalized.append(cleaned)
    return normalized


def _link_tier(url: str) -> int:
    if _FOOD_SIGNAL_RE.search(_hostname(url) or ""):
        return 0
    if is_link_hub(url):
        return 1
    return 2


def rank_profile_links(raw_links: Iterable[str]) -> list[str]:
    normalized = normalize_profile_links(raw_links)
    unwrapped = [unwrap_instagram_redirect(url) for url in normalized]
    candidates = [url for url in unwrapped if not is_social_or_storefront(url)]
    ranked = sorted(candidates, key=_link_tier)

    final: list[str] = []
    seen: set[str] = set()
    for url in ranked:
        if url in seen:
            continue
        seen.add(url)
        final.append(url)
    return final[:MAX_RANKED_PROFILE_LINKS]


def extract_recipe_like_anchors(html: str, base_url: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    hrefs: list[str] = []

    for anchor in soup.find_all("a", href=True):
        href = anchor["href"].strip()
        if not href or href.startswith("#"):
            continue
        absolute = urljoin(base_url, href)
        parsed = urlsplit(absolute)
        if parsed.scheme.casefold() != "https" or not parsed.hostname:
            continue
        text = anchor.get_text(" ", strip=True)
        haystack = f"{parsed.path} {text}"
        if _FOOD_SIGNAL_RE.search(haystack):
            hrefs.append(absolute)

    seen: set[str] = set()
    result: list[str] = []
    for href in hrefs:
        if href in seen:
            continue
        seen.add(href)
        result.append(href)
    return result


def _anchor_tokens(path: str, text: str) -> set[str]:
    slug = path.replace("-", " ").replace("_", " ").replace("/", " ")
    return set(normalize_dish_name(f"{slug} {text}").split())


def rank_candidate_anchors(html: str, base_url: str, dish_name: str) -> list[str]:
    """Rank on-site anchors by overlap with the dish named by the Reel.

    A recipe permalink rarely contains a generic food word, while category and
    tag listings always do, so selecting on food words picks up navigation and
    discards the recipes themselves. Overlap with the dish name is the signal
    that actually separates them. Ordering only: `select_unique_match` remains
    the sole acceptance gate.
    """
    dish_tokens = set(normalize_dish_name(dish_name).split())
    if not dish_tokens:
        return []

    soup = BeautifulSoup(html, "html.parser")
    scored: list[tuple[int, int, str]] = []
    seen: set[str] = set()

    for order, anchor in enumerate(soup.find_all("a", href=True)):
        href = anchor["href"].strip()
        if not href or href.startswith("#"):
            continue
        absolute = urljoin(base_url, href)
        if absolute in seen:
            continue
        parsed = urlsplit(absolute)
        if parsed.scheme.casefold() != "https" or not parsed.hostname:
            continue
        if any(marker in parsed.path.casefold() for marker in TAXONOMY_PATH_MARKERS):
            continue
        text = anchor.get_text(" ", strip=True)
        overlap = len(dish_tokens & _anchor_tokens(parsed.path, text))
        if overlap == 0:
            continue
        seen.add(absolute)
        scored.append((-overlap, order, absolute))

    scored.sort()
    return [url for _, _, url in scored]


def build_search_urls(domain: str, dish_name: str) -> list[str]:
    query = quote(dish_name)
    return [
        f"https://{domain}/?s={query}",
        f"https://{domain}/search?q={query}",
    ]


def canonicalize_candidate_url(url: str) -> str:
    parsed = urlsplit(url)
    hostname = (parsed.hostname or "").casefold()
    path = parsed.path.rstrip("/") or "/"
    return urlunsplit((parsed.scheme.casefold(), hostname, path, "", ""))


def normalize_dish_name(name: str) -> str:
    decomposed = unicodedata.normalize("NFKD", name)
    stripped = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    lowered = stripped.casefold()
    no_punct = _PUNCT_RE.sub(" ", lowered)

    raw = no_punct.split()
    tokens: list[str] = []
    index = 0
    while index < len(raw):
        token = raw[index]
        # "15 Minute", "5 Ingredient": a prep-time or count qualifier the site
        # adds, never part of the dish. The numeral is dropped only alongside
        # its unit, because a bare numeral can itself name the dish and must
        # stay distinguishing ("7 Layer Dip" is not "5 Layer Dip").
        if (
            token.isdigit()
            and index + 1 < len(raw)
            and raw[index + 1] in _TIME_QUALIFIER_UNITS
        ):
            index += 2
            continue
        if token in _TIME_QUALIFIER_UNITS:
            index += 1
            continue
        if token not in _GENERIC_TITLE_TOKENS:
            tokens.append(token)
        index += 1
    return " ".join(tokens)


def _site_brand_label(domain: Optional[str]) -> Optional[str]:
    if not domain:
        return None
    host = domain.casefold()
    if host.startswith("www."):
        host = host[len("www."):]
    return host.split(".")[0] or None


def strip_site_brand(normalized_title: str, domain: Optional[str]) -> str:
    """Drop a trailing "by <brand>" naming the site the page was served from.

    Sites sign their own titles ("... Recipe by Tasty"), which the Reel never
    does. Only the fetched host's own label is removed, so a dish word can
    never be stripped by accident.
    """
    label = _site_brand_label(domain)
    if not label:
        return normalized_title

    tokens = normalized_title.split()
    while tokens and tokens[-1] == label:
        tokens.pop()
        if tokens and tokens[-1] == "by":
            tokens.pop()
    return " ".join(tokens)


def is_matching_title(
    candidate_title: str, dish_name: str, *, site_domain: Optional[str] = None
) -> bool:
    candidate_norm = strip_site_brand(normalize_dish_name(candidate_title), site_domain)
    dish_norm = normalize_dish_name(dish_name)
    if not dish_norm or not candidate_norm:
        return False
    if candidate_norm == dish_norm:
        return True

    dish_tokens = dish_norm.split()
    if len(dish_tokens) < 2:
        return False

    # Order-independent match only: any additional or missing substantive
    # (non-generic) token is treated as a distinct dish, favoring precision.
    return set(candidate_norm.split()) == set(dish_tokens)


@dataclass(frozen=True)
class RecipeCandidate:
    canonical_url: str
    title: str
    result: ExtractionResult


def select_unique_match(
    candidates: list[RecipeCandidate], dish_name: str
) -> Optional[RecipeCandidate]:
    deduped: dict[tuple[str, str], RecipeCandidate] = {}
    for candidate in candidates:
        host = _hostname(candidate.canonical_url)
        key = (
            canonicalize_candidate_url(candidate.canonical_url),
            strip_site_brand(normalize_dish_name(candidate.title), host),
        )
        deduped.setdefault(key, candidate)

    matches = [
        candidate
        for candidate in deduped.values()
        if is_matching_title(
            candidate.title,
            dish_name,
            site_domain=_hostname(candidate.canonical_url),
        )
    ]
    if len(matches) != 1:
        return None
    return matches[0]


@dataclass(frozen=True)
class FetchedPage:
    final_url: str
    html: str


FetchHtml = Callable[[str], Awaitable[FetchedPage]]


async def _default_fetch_html(url: str) -> FetchedPage:
    result = await safe_fetch(url, HTML_POLICY, deadline_seconds=15)
    return FetchedPage(
        final_url=result.final_url,
        html=result.body.decode("utf-8", errors="replace"),
    )


async def find_creator_site_recipe(
    profile_links: Iterable[str],
    dish_name: str,
    *,
    fetch_html: FetchHtml = _default_fetch_html,
) -> Optional[ExtractionResult]:
    if not isinstance(dish_name, str) or not dish_name.strip():
        return None

    ranked_links = rank_profile_links(profile_links)
    if not ranked_links:
        return None

    domains: list[str] = []
    allowed_hosts: dict[str, set[str]] = {}
    entry_urls: dict[str, list[str]] = {}
    hub_traversed = False

    def _register(domain: str, host: str, url: str) -> None:
        if domain not in allowed_hosts:
            if len(domains) >= MAX_CREATOR_SITE_DOMAINS:
                return
            domains.append(domain)
            allowed_hosts[domain] = {host}
            entry_urls[domain] = []
        elif host not in allowed_hosts[domain]:
            return
        entry_urls[domain].append(url)

    for link in ranked_links:
        host = _hostname(link)
        if not host:
            continue
        if is_link_hub(link):
            if hub_traversed:
                continue
            hub_traversed = True
            try:
                page = await fetch_html(link)
            except PublicWebError:
                continue
            for anchor in extract_recipe_like_anchors(page.html, page.final_url):
                if is_social_or_storefront(anchor) or is_link_hub(anchor):
                    continue
                anchor_host = _hostname(anchor)
                if not anchor_host:
                    continue
                _register(anchor_host, anchor_host, anchor)
        else:
            _register(host, host, link)

    candidates: list[RecipeCandidate] = []
    pages_fetched = 0

    for domain in domains:
        if pages_fetched >= MAX_CANDIDATE_PAGES:
            break

        # Search-result pages are purpose-built to surface the dish; landing
        # pages are generic and can burn the page budget on irrelevant
        # anchors before a search page is ever reached. Try search first.
        queue = build_search_urls(domain, dish_name)
        for url in entry_urls[domain]:
            if url not in queue:
                queue.append(url)

        index = 0
        while index < len(queue) and pages_fetched < MAX_CANDIDATE_PAGES:
            candidate_url = queue[index]
            index += 1

            candidate_host = _hostname(candidate_url)
            if candidate_host is None:
                continue
            if candidate_host != domain and candidate_host not in allowed_hosts[domain]:
                continue

            pages_fetched += 1
            try:
                page = await fetch_html(candidate_url)
            except PublicWebError:
                continue

            final_host = _hostname(page.final_url)
            if final_host is None:
                continue
            if final_host != domain and final_host not in allowed_hosts[domain]:
                continue
            allowed_hosts[domain].add(final_host)

            parsed = parse_recipes_from_html(
                page.html, source_url=candidate_url, final_url=page.final_url
            )
            for recipe in parsed.recipes:
                candidates.append(
                    RecipeCandidate(
                        canonical_url=page.final_url,
                        title=recipe.name,
                        result=parsed,
                    )
                )

            for anchor in rank_candidate_anchors(page.html, page.final_url, dish_name):
                if is_social_or_storefront(anchor) or is_link_hub(anchor):
                    continue
                anchor_host = _hostname(anchor)
                if anchor_host is None:
                    continue
                if anchor_host == domain or anchor_host in allowed_hosts[domain]:
                    allowed_hosts[domain].add(anchor_host)
                    if anchor not in queue:
                        queue.append(anchor)

    match = select_unique_match(candidates, dish_name)
    if match is None:
        return None

    matched_recipe = next(
        recipe for recipe in match.result.recipes if recipe.name == match.title
    )
    return ExtractionResult(
        source_url=match.result.source_url,
        final_url=match.canonical_url,
        title=match.result.title,
        image_url=match.result.image_url,
        recipe_node_count=1,
        recipes=[matched_recipe],
    )
