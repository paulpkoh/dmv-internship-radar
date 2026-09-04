import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from src.match import category, evaluate, location_status, relevance
from src.models import Job


def check(cases, fn, label):
    bad = []
    for args, want in cases:
        got = fn(*args) if isinstance(args, tuple) else fn(args)
        if got != want:
            bad.append(f"  {args!r}\n     want={want!r} got={got!r}")
    if bad:
        print(f"FAIL {label}:\n" + "\n".join(bad))
    return len(bad)


def test_location():
    cases = [
        ("Rockville, MD", "in_scope"),
        ("Baltimore, Maryland", "in_scope"),
        ("Washington, DC", "in_scope"),
        ("Washington, D.C.", "in_scope"),
        ("Gaithersburg, MD, United States", "in_scope"),
        ("College Park, MD", "in_scope"),
        ("Bethesda, Maryland, US", "in_scope"),
        ("Arlington, VA", "in_scope"),
        ("McLean, Virginia", "in_scope"),
        ("Reston, VA | Remote", "in_scope"),
        ("Laurel, MD", "in_scope"),
        ("Frederick, MD", "in_scope"),
        ("Silver Spring, MD", "in_scope"),
        ("DC Metro Area", "in_scope"),
        ("Columbia, MD or Remote", "in_scope"),
        ("Boston, MA; Rockville, MD", "in_scope"),
        # Out of the commute radius
        ("Blacksburg, VA", "out"),
        ("Richmond, VA", "out"),
        ("Charlottesville, VA", "out"),
        ("Norfolk, VA", "out"),
        ("Wilmington, DE", "out"),
        ("Newark, DE", "out"),
        ("Cumberland, MD", "out"),
        ("Salisbury, MD", "out"),
        ("San Francisco, CA", "out"),
        ("Seattle, WA", "out"),
        ("Cambridge, MA", "out"),
        ("London, United Kingdom", "out"),
        # Remote handling
        ("Remote", "remote"),
        ("Remote - US", "remote"),
        ("Fully Remote (United States)", "remote"),
        ("Remote - EMEA", "out"),
        ("Remote, Canada", "out"),
        ("Remote - Bangalore, India", "out"),
        ("", "unknown"),
    ]
    return check(cases, location_status, "location_status")


def test_category():
    cases = [
        (("Software Engineering Intern", ""), "internship"),
        (("2027 Summer Intern - Machine Learning", ""), "internship"),
        (("Data Science Co-op", ""), "internship"),
        (("Bioinformatics Internship (Summer)", ""), "internship"),
        (("Undergraduate Research Assistant", ""), "internship"),
        (("Summer 2027 Analyst Program", ""), "internship"),
        (("Student Worker - IT Support", ""), "internship"),
        (("Research Assistant, Part-Time", ""), "part_time_research"),
        (("Lab Assistant", ""), "part_time_research"),
        # Not a fit
        (("Senior Machine Learning Engineer", ""), ""),
        (("Director of Data Science", ""), ""),
        (("Internal Medicine Physician", ""), ""),
        (("International Regulatory Affairs Manager", ""), ""),
        (("Postdoctoral Fellow, Computational Biology", ""), ""),
        (("Staff Software Engineer", ""), ""),
        (("Scientist III", ""), ""),
        (("Data Engineer", ""), ""),
        # Description rescue
        (("Analytics Associate", "This is an internship for current undergraduates."), "internship"),
    ]
    return check(cases, category, "category")


def test_relevance():
    bad = 0
    hi, _ = relevance("Machine Learning Intern", "PyTorch, deep learning, Python")
    lo, _ = relevance("Warehouse Associate Intern", "Lift boxes and manage inventory.")
    if hi < 20:
        print(f"FAIL relevance: ML intern scored only {hi}"); bad += 1
    if lo >= 6:
        print(f"FAIL relevance: warehouse role scored {lo}, should be under 6"); bad += 1
    bio, _ = relevance("Bioinformatics Intern", "Analyze genomic sequencing data with Python.")
    if bio < 20:
        print(f"FAIL relevance: bioinformatics intern scored only {bio}"); bad += 1
    return bad


def test_evaluate():
    bad = 0

    keep = evaluate(Job(title="Machine Learning Intern", company="Novavax",
                        company_slug="novavax", location="Gaithersburg, MD",
                        url="https://x/1", source="greenhouse",
                        description="Build predictive models in Python using PyTorch."))
    if keep is None or keep.category != "internship" or keep.relevance < 20:
        print(f"FAIL evaluate: expected a strong keep, got {keep}"); bad += 1

    for job, why in [
        (Job(title="Machine Learning Intern", company="X", company_slug="x",
             location="Blacksburg, VA", url="u", source="greenhouse",
             description="PyTorch"), "far location"),
        (Job(title="Senior Data Scientist", company="X", company_slug="x",
             location="Rockville, MD", url="u", source="greenhouse",
             description="Python machine learning"), "senior role"),
        (Job(title="Facilities Intern", company="X", company_slug="x",
             location="Rockville, MD", url="u", source="greenhouse",
             description="Maintain HVAC systems and coordinate building repairs and janitorial vendors."), "irrelevant"),
    ]:
        if evaluate(job) is not None:
            print(f"FAIL evaluate: should have dropped ({why}): {job.title}"); bad += 1

    # Location missing on the posting, but the company sits in Rockville.
    fallback = evaluate(Job(title="Bioinformatics Intern", company="X", company_slug="x",
                            location="", company_location="Rockville, MD",
                            url="u", source="greenhouse",
                            description="Genomic data analysis in Python."))
    if fallback is None:
        print("FAIL evaluate: company-location fallback did not keep the job"); bad += 1

    remote = evaluate(Job(title="Software Engineering Intern", company="X", company_slug="x",
                          location="Remote - US", url="u", source="greenhouse",
                          description="Python backend development."))
    if remote is None or not remote.remote:
        print("FAIL evaluate: US-remote internship should be kept and flagged remote"); bad += 1

    return bad


if __name__ == "__main__":
    total = test_location() + test_category() + test_relevance() + test_evaluate()
    print("ALL MATCH TESTS PASSED" if total == 0 else f"{total} FAILURES")
    raise SystemExit(1 if total else 0)
