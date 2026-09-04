"""Connector, store and site tests. No network: net.get_json/get_text are stubbed."""

import json, sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from src import net, site, store
from src.ats import ashby, greenhouse, lever, smartrecruiters, workable
from src.models import Company, Job

FAILURES = []


def fail(msg):
    FAILURES.append(msg)
    print("FAIL " + msg)


COMPANY = Company(name="Test Bio", domain="testbio.com", city="Rockville", state="MD")


def stub_json(payload):
    net.get_json = lambda url, **kw: payload


def test_greenhouse():
    stub_json({"jobs": [{
        "id": 1, "title": "Machine Learning Intern",
        "location": {"name": "Rockville, MD"},
        "absolute_url": "https://boards.greenhouse.io/testbio/jobs/1",
        "updated_at": "2026-08-14T10:00:00-04:00",
        "content": "&lt;p&gt;Work on &lt;b&gt;PyTorch&lt;/b&gt; models.&lt;/p&gt;",
        "departments": [{"name": "Data Science"}],
    }]})
    jobs = greenhouse.fetch("testbio", COMPANY)
    if len(jobs) != 1:
        return fail(f"greenhouse returned {len(jobs)} jobs")
    j = jobs[0]
    if j.title != "Machine Learning Intern": fail("greenhouse title")
    if j.location != "Rockville, MD": fail(f"greenhouse location: {j.location!r}")
    if j.posted_at != "2026-08-14": fail(f"greenhouse date: {j.posted_at!r}")
    if "PyTorch" not in j.description: fail(f"greenhouse description: {j.description!r}")
    if "<" in j.description: fail("greenhouse left HTML tags in the description")
    if j.department != "Data Science": fail("greenhouse department")


def test_lever():
    stub_json([{
        "text": "Bioinformatics Co-op", "hostedUrl": "https://jobs.lever.co/testbio/abc",
        "createdAt": 1755100000000,
        "categories": {"location": "Bethesda, MD", "team": "Research"},
        "descriptionPlain": "Analyze sequencing data.",
        "lists": [{"content": "<li>Python</li><li>genomics</li>"}],
    }])
    jobs = lever.fetch("testbio", COMPANY)
    if len(jobs) != 1: return fail("lever count")
    j = jobs[0]
    if j.location != "Bethesda, MD": fail(f"lever location {j.location!r}")
    if "Python" not in j.description: fail("lever did not fold in list content")
    if not j.posted_at.startswith("2025") and not j.posted_at.startswith("2026"):
        fail(f"lever epoch-ms date parsed as {j.posted_at!r}")


def test_ashby():
    stub_json({"jobs": [{
        "title": "Data Science Intern", "location": "Remote - US",
        "jobUrl": "https://jobs.ashbyhq.com/testbio/xyz",
        "publishedAt": "2026-08-01T00:00:00.000Z",
        "descriptionPlain": "SQL and pandas.", "isRemote": True, "department": "Data",
    }]})
    jobs = ashby.fetch("testbio", COMPANY)
    if len(jobs) != 1: return fail("ashby count")
    if not jobs[0].remote: fail("ashby remote flag")
    if jobs[0].posted_at != "2026-08-01": fail(f"ashby date {jobs[0].posted_at!r}")


def test_workable():
    stub_json({"jobs": [{
        "title": "Software Engineering Intern", "city": "Baltimore", "state": "MD",
        "country": "USA", "url": "https://apply.workable.com/testbio/j/ABC/",
        "published_on": "2026-07-30", "description": "<p>Build APIs in Python.</p>",
        "requirements": "<ul><li>CS coursework</li></ul>", "telecommuting": False,
    }]})
    jobs = workable.fetch("testbio", COMPANY)
    if len(jobs) != 1: return fail("workable count")
    if jobs[0].location != "Baltimore, MD, USA": fail(f"workable location {jobs[0].location!r}")
    if "Python" not in jobs[0].description: fail("workable description")


def test_smartrecruiters():
    stub_json({"totalFound": 1, "content": [{
        "id": "743999", "name": "AI/ML Intern",
        "location": {"city": "Gaithersburg", "region": "MD", "country": "us", "remote": False},
        "releasedDate": "2026-08-20T12:00:00.000Z",
        "ref": "https://api.smartrecruiters.com/v1/companies/TestBio/postings/743999",
        "department": {"label": "R&D"},
    }]})
    jobs = smartrecruiters.fetch("TestBio", COMPANY)
    if len(jobs) != 1: return fail("smartrecruiters count")
    j = jobs[0]
    if "Gaithersburg" not in j.location: fail(f"sr location {j.location!r}")
    if "api.smartrecruiters" in j.url: fail(f"sr url not rewritten for humans: {j.url}")


def test_malformed_input():
    """Every connector must survive garbage rather than crash the run."""
    for payload in (None, [], {}, {"jobs": None}, {"jobs": [None, "x", {}]}, "not json"):
        stub_json(payload)
        for mod, token in ((greenhouse, "t"), (lever, "t"), (ashby, "t"),
                           (workable, "t"), (smartrecruiters, "t")):
            try:
                mod.fetch(token, COMPANY)
            except Exception as exc:
                fail(f"{mod.__name__} crashed on {payload!r}: {exc}")


def test_merge_preserves_first_seen():
    old = Job(title="ML Intern", company="A", company_slug="a", location="Rockville, MD",
              url="https://x/1", source="greenhouse")
    old.first_seen = "2026-01-01T00:00:00+00:00"
    old.last_seen = "2026-09-04T00:00:00+00:00"

    same = Job(title="ML Intern", company="A", company_slug="a", location="Rockville, MD",
               url="https://x/1", source="greenhouse")
    fresh = Job(title="Data Intern", company="A", company_slug="a", location="Rockville, MD",
                url="https://x/2", source="greenhouse")

    current, added, gone = store.merge([old], [same, fresh])
    if len(added) != 1 or added[0].title != "Data Intern":
        fail(f"merge should report exactly the new posting, got {[j.title for j in added]}")
    kept = [j for j in current if j.id == old.id]
    if not kept: return fail("merge dropped an existing posting")
    if kept[0].first_seen != "2026-01-01T00:00:00+00:00":
        fail(f"merge lost first_seen: {kept[0].first_seen!r}")
    if store.is_new(kept[0]):
        fail("a job first seen in January should not be badged NEW")
    if not store.is_new(added[0]):
        fail("a job first seen just now should be badged NEW")

    # A posting that vanished long ago should be retired.
    stale = Job(title="Old Intern", company="A", company_slug="a", location="Rockville, MD",
                url="https://x/9", source="greenhouse")
    stale.first_seen = stale.last_seen = "2025-01-01T00:00:00+00:00"
    current2, _, gone2 = store.merge([stale], [])
    if not gone2 or current2:
        fail("merge should retire a posting that has been gone for months")


def test_site_build(tmp=pathlib.Path("/tmp/claude-0/radar-site-test.html")):
    jobs = []
    for i in range(3):
        j = Job(title=f"ML Intern {i}", company="Novavax", company_slug="novavax",
                location="Gaithersburg, MD", url=f"https://x/{i}", source="greenhouse",
                description="PyTorch </script><script>alert(1)</script>")
        j.category = "internship"; j.relevance = 24
        j.first_seen = j.last_seen = "2026-09-04T00:00:00+00:00"
        jobs.append(j)
    path = site.build(jobs, {"companies_tracked": 500, "boards_found": 90}, out=tmp)
    html = path.read_text()
    if "ML Intern 0" not in html: fail("site: job title missing from output")
    if "</script><script>alert(1)" in html:
        fail("site: raw </script> from job data was not neutralised")
    blob = html.split('<script id="data" type="application/json">')[1].split("</script>")[0]
    data = json.loads(blob.replace("<\\/", "</"))
    if len(data["jobs"]) != 3: fail("site: wrong job count in embedded JSON")
    if not data["programs"]: fail("site: programs panel is empty")
    if not data["jobs"][0]["isNew"]: fail("site: today's job is not marked new")


if __name__ == "__main__":
    for fn in [test_greenhouse, test_lever, test_ashby, test_workable, test_smartrecruiters,
               test_malformed_input, test_merge_preserves_first_seen, test_site_build]:
        fn()
    print("ALL PIPELINE TESTS PASSED" if not FAILURES else f"{len(FAILURES)} FAILURES")
    raise SystemExit(1 if FAILURES else 0)
