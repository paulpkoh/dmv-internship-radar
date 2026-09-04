"""Discovery regexes and the BioPharmGuy directory parser. No network."""

import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from src import directory
from src.discover import _extract

FAILURES = []
def fail(m):
    FAILURES.append(m); print("FAIL " + m)


SNIPPETS = [
    ('<a href="https://boards.greenhouse.io/macrogenics">Careers</a>', ("greenhouse", "macrogenics")),
    ('<script src="https://boards.greenhouse.io/embed/job_board/js?for=novavax"></script>'
     '<div id="grnhse_app"></div><iframe src="https://boards.greenhouse.io/embed/job_board?for=novavax"></iframe>',
     ("greenhouse", "novavax")),
    ('<a href="https://job-boards.greenhouse.io/emergentbiosolutions">Open roles</a>', ("greenhouse", "emergentbiosolutions")),
    ('fetch("https://boards-api.greenhouse.io/v1/boards/precigen/jobs")', ("greenhouse", "precigen")),
    ('<a href="https://jobs.lever.co/maxcyte/">See jobs</a>', ("lever", "maxcyte")),
    ('<a href="https://jobs.ashbyhq.com/clasp-therapeutics">Join us</a>', ("ashby", "clasp-therapeutics")),
    ('<a href="https://careers.smartrecruiters.com/Emmes">Careers</a>', ("smartrecruiters", "Emmes")),
    ('<iframe src="https://apply.workable.com/theradaptive/"></iframe>', ("workable", "theradaptive")),
    ('<a href="https://sapiosciences.recruitee.com/">Openings</a>', ("recruitee", "sapiosciences")),
    ('<a href="https://roosterbio.bamboohr.com/careers">Work here</a>', ("bamboohr", "roosterbio")),
    ('<a href="https://ats.rippling.com/junebrain/jobs">Careers</a>', ("rippling", "junebrain")),
    ('<a href="https://leidos.wd5.myworkdayjobs.com/en-US/External">Search jobs</a>',
     ("workday", "leidos|wd5|External")),
    ('<a href="https://astrazeneca.wd3.myworkdayjobs.com/Careers">Careers</a>',
     ("workday", "astrazeneca|wd3|Careers")),
]


def test_extract():
    for html, want in SNIPPETS:
        got = _extract(html)
        if want not in got:
            fail(f"_extract missed {want} in {html[:70]!r} -> {got}")


def test_extract_ignores_furniture():
    noise = ('<a href="https://boards.greenhouse.io/embed/job_board">x</a>'
             '<a href="https://www.linkedin.com/jobs">LinkedIn</a>'
             '<a href="https://jobs.lever.co/">Lever</a>')
    got = _extract(noise)
    for source, token in got:
        if token.lower() in {"embed", "jobs", "job_board", ""}:
            fail(f"_extract accepted URL furniture as a token: {source}:{token}")


def test_directory_parser():
    html = """
    <table>
      <tr><th>Company</th><th>Location</th><th>Description</th></tr>
      <tr><td><a href="http://www.macrogenics.com">MacroGenics</a></td>
          <td>Rockville, MD</td><td>Bispecific antibodies</td></tr>
      <tr><td><a href="https://novavax.com/">Novavax</a></td>
          <td>Gaithersburg, MD</td><td>Virus-like Particles, Micelles</td></tr>
      <tr><td><a href="https://www.lunainc.com">Luna Innovations</a></td>
          <td>Blacksburg, VA</td><td>Sensors and systems</td></tr>
      <tr><td>No link here</td><td>Nowhere, XX</td><td>-</td></tr>
    </table>"""
    from bs4 import BeautifulSoup
    got = directory._dedupe(directory._from_table(BeautifulSoup(html, "html.parser")))
    if len(got) != 3:
        return fail(f"directory parser found {len(got)} companies, expected 3")
    by_name = {c.name: c for c in got}
    mg = by_name.get("MacroGenics")
    if mg is None: return fail("directory parser lost MacroGenics")
    if mg.domain != "macrogenics.com": fail(f"domain not normalised: {mg.domain!r}")
    if (mg.city, mg.state) != ("Rockville", "MD"): fail(f"location parsed as {mg.city!r},{mg.state!r}")
    if "antibod" not in mg.category.lower(): fail(f"description lost: {mg.category!r}")
    if by_name["Novavax"].domain != "novavax.com": fail("trailing-slash domain not normalised")


def test_split_location():
    cases = [("Rockville, MD", ("Rockville", "MD")),
             ("Washington, DC", ("Washington", "DC")),
             ("Sparks Glencoe, MD", ("Sparks Glencoe", "MD")),
             ("", ("", ""))]
    for raw, want in cases:
        got = directory._split_location(raw)
        if got != want:
            fail(f"_split_location({raw!r}) = {got!r}, want {want!r}")


if __name__ == "__main__":
    for fn in [test_extract, test_extract_ignores_furniture, test_directory_parser, test_split_location]:
        fn()
    print("ALL DISCOVERY TESTS PASSED" if not FAILURES else f"{len(FAILURES)} FAILURES")
    raise SystemExit(1 if FAILURES else 0)
