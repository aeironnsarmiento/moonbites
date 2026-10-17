"""Reading a blog page's own words when its structured data gives us no recipe.

Two things come out of a page here: its title, which stands in for the dish
name when the page competes to be a **Linked Recipe**, and its main text, which
is what Gemini reads when the page falls back to parsing.
"""

from __future__ import annotations

import re
from typing import Any, Iterable, Optional

from bs4 import BeautifulSoup, Tag

from ...schemas.extract import JsonLdBlock
from ...utils.text import clean_text


MAX_PAGE_TEXT_CHARS = 30_000

ARTICLE_TYPES = frozenset({"article", "blogposting", "newsarticle"})

_NOISE_TAGS = (
    "script",
    "style",
    "noscript",
    "template",
    "svg",
    "iframe",
    "nav",
    "aside",
    "form",
    "footer",
)
_COMMENT_THREAD_MARKERS = frozenset(
    {
        "comments",
        "comment-list",
        "commentlist",
        "comments-area",
        "comment-respond",
        "respond",
        "disqus_thread",
    }
)
_WHITESPACE_RE = re.compile(r"\s+")
# "Dish Name | Site Name": a trailing segment after a spaced separator.
_TRAILING_SEGMENT_RE = re.compile(r"^(?P<head>.*\S)\s+[|\-\u2013\u2014:\u00b7\u2022]\s+(?P<tail>\S.*)$")
_NON_ALNUM_RE = re.compile(r"[\W_]+", re.UNICODE)


def _node_types(node: dict) -> set[str]:
    value = node.get("@type")
    values = value if isinstance(value, list) else [value]
    return {item.casefold() for item in values if isinstance(item, str)}


def _iter_nodes(payload: Any) -> Iterable[dict]:
    if isinstance(payload, list):
        for item in payload:
            yield from _iter_nodes(item)
    elif isinstance(payload, dict):
        yield payload
        graph = payload.get("@graph")
        if graph is not None:
            yield from _iter_nodes(graph)


def _article_headline(blocks: list[JsonLdBlock]) -> Optional[str]:
    for block in blocks:
        if block.parsed is None:
            continue
        for node in _iter_nodes(block.parsed):
            if _node_types(node) & ARTICLE_TYPES:
                headline = clean_text(node.get("headline"))
                if headline:
                    return headline
    return None


def _squash(value: str) -> str:
    return _NON_ALNUM_RE.sub("", value.casefold())


def _meta_content(soup: BeautifulSoup, prop: str) -> Optional[str]:
    tag = soup.find("meta", attrs={"property": prop})
    return clean_text(tag.get("content")) if isinstance(tag, Tag) else None


def _strip_site_suffix(title: str, brands: set[str]) -> str:
    """Drop trailing " | Site Name" segments that name the site, not the dish."""
    while (match := _TRAILING_SEGMENT_RE.match(title)) and _squash(
        match.group("tail")
    ) in brands:
        title = match.group("head")
    return title


def _site_brands(soup: BeautifulSoup, host: Optional[str]) -> set[str]:
    brands = set()
    site_name = _meta_content(soup, "og:site_name")
    if site_name:
        brands.add(_squash(site_name))
    if host:
        label = host.casefold().removeprefix("www.").split(".")[0]
        if label:
            brands.add(label)
    brands.discard("")
    return brands


def extract_page_title(
    soup: BeautifulSoup, blocks: list[JsonLdBlock], *, host: Optional[str] = None
) -> Optional[str]:
    """The page's own name for itself: article headline, then og:title, then <title>.

    The headline comes first because sites often fill og:title and <title> with
    their own brand rather than the dish. Those two also usually carry a
    trailing site name ("Dish | Site"), which is removed so the title can match
    the dish a post names.
    """
    headline = _article_headline(blocks)
    if headline:
        return headline

    title = _meta_content(soup, "og:title")
    if not title and soup.title and soup.title.string:
        title = clean_text(soup.title.string)
    if not title:
        return None
    return _strip_site_suffix(title, _site_brands(soup, host))


def _is_comment_thread(node: Tag) -> bool:
    markers = {str(node.get("id") or "").casefold()}
    markers.update(str(value).casefold() for value in node.get("class") or [])
    return bool(markers & _COMMENT_THREAD_MARKERS)


def _main_container(soup: BeautifulSoup) -> tuple[Tag, bool]:
    """Returns (container, is_whole_body)."""
    main = soup.find("main")
    if isinstance(main, Tag):
        return main, False

    articles = [node for node in soup.find_all("article") if isinstance(node, Tag)]
    if articles:
        return max(articles, key=lambda node: len(node.get_text())), False

    return soup.body or soup, True


def extract_main_text(soup: BeautifulSoup) -> str:
    """The page's main content as plain text, one block per line, capped.

    Mutates ``soup``; callers pass a soup they no longer need.
    """
    container, is_whole_body = _main_container(soup)

    noise = list(container.find_all(_NOISE_TAGS))
    noise.extend(
        node
        for node in container.find_all(True)
        if isinstance(node, Tag) and _is_comment_thread(node)
    )
    # A site header only wraps navigation when we are reading the whole body;
    # inside <main> or <article> a <header> holds the post's own title.
    if is_whole_body:
        noise.extend(container.find_all("header"))
    for node in noise:
        if not node.decomposed:
            node.decompose()

    lines = [
        collapsed
        for raw in container.get_text("\n").splitlines()
        if (collapsed := _WHITESPACE_RE.sub(" ", raw).strip())
    ]
    return "\n".join(lines)[:MAX_PAGE_TEXT_CHARS]
