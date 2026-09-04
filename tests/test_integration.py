"""End-to-end dry run with the network stubbed out.

Proves the wiring in run.py holds together: company list -> discovery cache ->
board scrape -> filtering -> merge -> rendered page.
"""

import json, sys, pathlib, tempfile
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import run as radar
from src import directory, discover, match, net, seeds, site, store
from src.ats import greenhouse, htmlscan, usajobs
from src.models import Company, Job

FAILURES = []
def fail(m):
    FAILURES.append(m); print("FAIL " + m)


FAKE_BOARD = {
    "novavax": {"jobs": [
        {"id": 1, "title": "Machine Learning Intern", "location": {"name": "Gaithersburg, MD"},
         "absolute_url": "https://boards.greenhouse.io/novavax/jobs/1",
         "updated_at": "2026-08-14T10:00:00-04:00",
         "content": "Build predictive models in Python with PyTorch over assay data.",
         "departments": [{"name": "Data Science"}]},
        {"id": 2, "title": "Senior Director, Regulatory Affairs", "location": {"name": "Gaithersburg, MD"},
         "absolute_url": "https://boards.greenhouse.io/novavax/jobs/2",
         "updated_at": "2026-08-14T10:00:00-04:00", "content": "Lead submissions."},
        {"id": 3, "title": "Software Engineering Intern", "location": {"name": "Blacksburg, VA"},
         "absolute_url": "https://boards.greenhouse.io/novavax/jobs/3",
         "updated_at": "2026-08-14T10:00:00-04:00", "content": "Python backend."},
        {"id": 4, "title": "Warehouse Intern", "location": {"name": "Rockville, MD"},
         "absolute_url": "https://boards.greenhouse.io/novavax/jobs/4",
         "updated_at": "2026-08-14T10:00:00-04:00",
         "content": "Receive shipments, stock shelves, operate a pallet jack."},
    ]},
}


def run_dry():
    companies = [
        Company(name="Novavax", domain="novavax.com", city="Gaithersburg", state="MD"),
        Company(name="Tiny Bio", domain="tinybio.com", city="Rockville", state="MD"),
    ]
    cache = {
        "novavax": {"slug": "novavax", "name": "Novavax", "domain": "novavax.com",
                    "source": "greenhouse", "token": "novavax", "careers_url": "",
                    "checked_at": "2026-09-04T00:00:00+00:00"},
        "tiny-bio": {"slug": "tiny-bio", "name": "Tiny Bio", "domain": "tinybio.com",
                     "source": "html", "token": "",
                     "careers_url": "https://tinybio.com/careers",
                     "checked_at": "2026-09-04T00:00:00+00:00"},
    }

    def fake_get_json(url, **kw):
        for token, payload in FAKE_BOARD.items():
            if f"/boards/{token}/jobs" in url:
                return payload
        return None

    def fake_get_text(url, **kw):
        if "tinybio.com/careers" in url:
            return ('<html><body><h1>Careers</h1>'
                    '<a href="/jobs/bioinformatics-intern">Bioinformatics Intern (Summer)</a>'
                    '<a href="/privacy">Privacy policy</a></body></html>')
        return None

    net.get_json, net.get_text = fake_get_json, fake_get_text
    usajobs.available = lambda: False

    raw = radar.scrape(companies, cache)
    matched = match.evaluate_all(raw)
    return raw, matched


def test_pipeline():
    raw, matched = run_dry()
    if len(raw) != 5:
        fail(f"expected 5 raw postings (4 greenhouse + 1 careers link), got {len(raw)}")

    titles = sorted(j.title for j in matched)
    expected = ["Bioinformatics Intern (Summer)", "Machine Learning Intern"]
    if titles != expected:
        fail(f"filtering kept {titles}, expected {expected}")

    for j in matched:
        if j.title.startswith("Bioinformatics") and j.confidence != "low":
            fail("careers-page hit should be flagged low confidence")
        if j.title.startswith("Machine Learning"):
            if j.relevance < 20: fail(f"ML intern relevance too low: {j.relevance}")
            if j.category != "internship": fail("ML intern miscategorised")


def test_merge_and_render():
    _, matched = run_dry()
    current, added, gone = store.merge([], matched)
    if len(added) != len(matched):
        fail("first run should report every posting as new")

    # Second run, same postings: nothing should be reported as new.
    current2, added2, _ = store.merge(current, matched)
    if added2:
        fail(f"second identical run reported {len(added2)} new postings, expected 0")
    if any(j.first_seen != current[0].first_seen for j in current2 if j.id == current[0].id):
        fail("first_seen changed between runs")

    with tempfile.TemporaryDirectory() as tmp:
        out = pathlib.Path(tmp) / "index.html"
        site.build(current2, {"companies_tracked": 2, "boards_found": 1}, out=out)
        html = out.read_text()
        if "Machine Learning Intern" not in html:
            fail("rendered page is missing a matched posting")
        if "Warehouse Intern" in html:
            fail("rendered page leaked a filtered-out posting")
        if "Senior Director" in html:
            fail("rendered page leaked a senior role")


def test_company_list_falls_back():
    directory.fetch = lambda *a, **k: []          # simulate the directory being down
    companies = radar.build_company_list()
    if len(companies) < 150:
        fail(f"fallback company list only had {len(companies)} entries")
    names = {c.name for c in companies}
    for must in ("NIST", "Leidos", "Johns Hopkins Applied Physics Laboratory", "MacroGenics"):
        if must not in names:
            fail(f"fallback list is missing {must}")
    slugs = [c.slug for c in companies]
    if len(slugs) != len(set(slugs)):
        fail("fallback list contains duplicate slugs")


if __name__ == "__main__":
    for fn in [test_pipeline, test_merge_and_render, test_company_list_falls_back]:
        fn()
    print("ALL INTEGRATION TESTS PASSED" if not FAILURES else f"{len(FAILURES)} FAILURES")
    raise SystemExit(1 if FAILURES else 0)
