from agents.hermes import sanitize_web_results


def test_sanitize_web_results_drops_blocked_urls_and_snippets():
    results = [
        {"title": "Safe article", "url": "https://example.com/post", "snippet": "Public benchmark data."},
        {"title": "Tenant portal", "url": "https://acme.nxt8.internal/report", "snippet": "Internal link"},
        {"title": "Client file", "url": "https://example.com/view", "snippet": "session_id=abc123 leaked"},
        {"title": "Private email", "url": "https://example.com/case", "snippet": "contact @myclient.com for access"},
        {"title": "Roadmap", "url": "https://example.com/tenant/dashboard", "snippet": "Overview"},
    ]

    cleaned = sanitize_web_results(results)
    assert cleaned == [
        {"title": "Safe article", "url": "https://example.com/post", "snippet": "Public benchmark data."}
    ]


def test_sanitize_web_results_normalizes_fields():
    cleaned = sanitize_web_results([
        {"title": "  Market update  ", "url": " https://example.com/news ", "snippet": "  Fresh data.  "}
    ])
    assert cleaned == [
        {"title": "Market update", "url": "https://example.com/news", "snippet": "Fresh data."}
    ]


def test_sanitize_web_results_can_blank_fetch_content():
    cleaned = sanitize_web_results([
        {"snippet": "tenant_id=client-abc leaked in body"}
    ])
    assert cleaned == []