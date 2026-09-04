#!/usr/bin/env python3
"""DMV Internship Radar - build the company list, scrape every board, rebuild the site.

Usage:
    python run.py                 # normal run: discover (if stale), scrape, rebuild
    python run.py --force-discovery
    python run.py --skip-discovery
    python run.py --rebuild-site  # no network; regenerate docs/index.html from data/jobs.json
    python run.py --limit 40      # only look at the first N companies (for testing)
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from src import config, directory, discover, match, seeds, site, store  # noqa: E402
from src.ats import REGISTRY  # noqa: E402
from src.ats import htmlscan, smartrecruiters, usajobs  # noqa: E402
from src.models import Company, Job  # noqa: E402
from src import net  # noqa: E402

log = logging.getLogger("radar")


def build_company_list(refresh: bool = True) -> list[Company]:
    companies: list[Company] = []
    if refresh:
        companies = directory.fetch()
    if len(companies) < 50:
        cached = store.load_companies()
        snapshot = directory.load_snapshot()
        fallback = cached if len(cached) > len(snapshot) else snapshot
        if fallback:
            log.warning("Directory returned %d companies; using cached/snapshot list of %d",
                        len(companies), len(fallback))
            companies = fallback

    by_domain: dict[str, Company] = {}
    for c in companies + seeds.major_employers():
        if not c.domain:
            continue
        by_domain.setdefault(c.domain, c)
    # Seed entries win on tier/description if they collide with a directory row.
    for c in seeds.major_employers():
        if c.domain in by_domain:
            by_domain[c.domain] = c

    out = sorted(by_domain.values(), key=lambda c: c.name.lower())
    log.info("Watching %d companies", len(out))
    return out


def scrape(companies: list[Company], cache: dict[str, dict], use_html_fallback: bool = True) -> list[Job]:
    by_slug = {c.slug: c for c in companies}
    ats_targets: list[tuple[Company, str, str]] = []
    html_targets: list[tuple[Company, str]] = []

    for slug, rec in cache.items():
        company = by_slug.get(slug)
        if company is None:
            continue
        source = rec.get("source", "none")
        if source in REGISTRY and rec.get("token"):
            ats_targets.append((company, source, rec["token"]))
        elif source == "html" and rec.get("careers_url") and use_html_fallback:
            html_targets.append((company, rec["careers_url"]))

    log.info("Scraping %d ATS boards and %d careers pages", len(ats_targets), len(html_targets))

    def pull_ats(target: tuple[Company, str, str]) -> list[Job]:
        company, source, token = target
        try:
            return REGISTRY[source].fetch(token, company)
        except Exception as exc:  # noqa: BLE001
            log.debug("%s (%s) failed: %s", company.name, source, exc)
            return []

    def pull_html(target: tuple[Company, str]) -> list[Job]:
        company, url = target
        try:
            return htmlscan.scan(url, company)
        except Exception as exc:  # noqa: BLE001
            log.debug("%s careers page failed: %s", company.name, exc)
            return []

    jobs = net.flatten(net.parallel(pull_ats, ats_targets, label="boards"))
    if html_targets:
        jobs += net.flatten(net.parallel(pull_html, html_targets, label="careers pages", jitter=0.2))

    if usajobs.available():
        jobs += usajobs.fetch_all()
    else:
        log.info("USAJOBS skipped (set USAJOBS_API_KEY and USAJOBS_EMAIL to include federal roles)")

    log.info("Collected %d raw postings", len(jobs))
    return jobs


def enrich(jobs: list[Job], cache: dict[str, dict]) -> None:
    """SmartRecruiters list responses have no description; fill them in for
    the handful of postings that survived the first pass."""
    targets = [j for j in jobs if j.source == "smartrecruiters" and len(j.description) < 100]
    if not targets:
        return
    tokens = {rec["slug"]: rec["token"] for rec in cache.values() if rec.get("source") == "smartrecruiters"}

    def do(job: Job) -> None:
        token = tokens.get(job.company_slug)
        if token:
            smartrecruiters.enrich(token, job)

    net.parallel(do, targets, label="enrich")


def main() -> int:
    ap = argparse.ArgumentParser(description="DMV Internship Radar")
    ap.add_argument("--skip-discovery", action="store_true", help="use the cached ATS map as-is")
    ap.add_argument("--force-discovery", action="store_true", help="re-check every company's board")
    ap.add_argument("--rebuild-site", action="store_true", help="regenerate the page from stored data only")
    ap.add_argument("--no-html-fallback", action="store_true", help="skip plain careers-page scanning")
    ap.add_argument("--limit", type=int, default=0, help="only process the first N companies")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s  %(levelname)-7s %(message)s",
        datefmt="%H:%M:%S",
    )
    logging.getLogger("urllib3").setLevel(logging.ERROR)

    previous, history = store.load_jobs()

    if args.rebuild_site:
        stats = {"companies_tracked": len(store.load_companies()),
                 "boards_found": sum(1 for r in store.load_ats().values() if r.get("token"))}
        path = site.build(previous, stats)
        log.info("Rebuilt %s from %d stored postings", path, len(previous))
        return 0

    companies = build_company_list()
    if args.limit:
        companies = companies[: args.limit]
    store.save_companies(companies)

    cache = store.load_ats()
    if not args.skip_discovery:
        cache = discover.discover(companies, cache, force=args.force_discovery)
        store.save_ats(cache)

    raw = scrape(companies, cache, use_html_fallback=not args.no_html_fallback)
    enrich(raw, cache)
    matched = match.evaluate_all(raw)
    log.info("%d postings survived filtering", len(matched))

    current, added, gone = store.merge(previous, matched)

    boards = sum(1 for r in cache.values() if r.get("token"))
    stats = {
        "companies_tracked": len(companies),
        "boards_found": boards,
        "raw_postings": len(raw),
        "matched": len(matched),
        "new": len(added),
        "expired": len(gone),
    }
    notice = ""
    if not current:
        notice = ("No matching postings yet. Either this is the first run, or nothing "
                  "open right now clears the filters in src/config.py.")
    store.save_jobs(current, history, stats)
    site.build(current, stats, notice=notice)

    log.info("=" * 62)
    log.info("Companies watched : %d  (%d with a live job board)", len(companies), boards)
    log.info("Raw postings seen : %d", len(raw))
    log.info("Matching your major: %d", len(matched))
    log.info("New since last run: %d", len(added))
    for job in added[:15]:
        log.info("   NEW  %-58s %s", job.title[:58], job.company)
    log.info("Site written to docs/index.html")
    log.info("=" * 62)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
