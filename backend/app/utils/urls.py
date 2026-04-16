from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


TRACKING_QUERY_PARAMS = {
    "fbclid",
    "gclid",
    "mc_cid",
    "mc_eid",
    "mkt_tok",
    "ref",
    "spm",
    "utm_campaign",
    "utm_content",
    "utm_id",
    "utm_medium",
    "utm_name",
    "utm_source",
    "utm_term",
}


def canonicalize_url(value: str) -> str:
    parsed = urlsplit(value.strip())

    hostname = (parsed.hostname or "").lower()
    scheme = parsed.scheme.lower()
    path = parsed.path or "/"

    if path != "/":
        path = path.rstrip("/") or "/"

    include_port = parsed.port and not (
        (scheme == "http" and parsed.port == 80)
        or (scheme == "https" and parsed.port == 443)
    )
    netloc = f"{hostname}:{parsed.port}" if include_port else hostname

    query_pairs = [
        (key, value)
        for key, value in parse_qsl(parsed.query, keep_blank_values=False)
        if key.lower() not in TRACKING_QUERY_PARAMS
    ]
    query = urlencode(sorted(query_pairs))

    return urlunsplit((scheme, netloc, path, query, ""))
