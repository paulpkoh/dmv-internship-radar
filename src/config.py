"""All tunable knobs for the radar live here.

Edit this file to change what counts as "close enough" or "relevant to me".
Nothing else in the codebase hardcodes these decisions.
"""

from __future__ import annotations

# --------------------------------------------------------------------------
# Source directory
# --------------------------------------------------------------------------

BIOPHARMGUY_URL = "https://biopharmguy.com/links/company-by-location-dc-area.php"

# --------------------------------------------------------------------------
# Geography
# --------------------------------------------------------------------------
# Policy: a job is in scope if it is (a) in DC, (b) in an in-scope Maryland
# locality, (c) in an in-scope Northern Virginia locality, or (d) fully remote
# within the US. Everything else is dropped.

IN_SCOPE_STATES = {"MD", "DC", "VA"}

# Maryland localities within roughly an hour of Ellicott City / College Park.
MD_CITIES = {
    "aberdeen", "annapolis", "arbutus", "arnold", "baltimore", "beltsville",
    "bethesda", "bowie", "brooklandville", "burtonsville", "california",
    "camp springs", "canton", "catonsville", "chevy chase", "clarksburg",
    "clarksville", "cockeysville", "college park", "columbia", "crofton",
    "derwood", "dundalk", "edgewood", "eldersburg", "elkridge", "ellicott city",
    "emmitsburg", "fort meade", "fort washington", "frederick", "fulton",
    "gaithersburg", "gambrills", "germantown", "glen burnie", "greenbelt",
    "hagerstown", "halethorpe", "hanover", "hunt valley", "hyattsville",
    "ijamsville", "jessup", "kensington", "landover", "lanham", "largo",
    "laurel", "linthicum", "linthicum heights", "lutherville", "middle river",
    "middletown", "millersville", "monrovia", "national harbor", "new market",
    "north bethesda", "nottingham", "odenton", "olney", "owings mills",
    "oxon hill", "parkville", "pasadena", "pikesville", "poolesville",
    "potomac", "riverdale", "riverdale park", "rockville", "rosedale",
    "savage", "severn", "severna park", "silver spring", "sparks",
    "sparks glencoe", "suitland", "sykesville", "takoma park", "temple hills",
    "timonium", "towson", "upper marlboro", "waldorf", "walkersville",
    "westminster", "wheaton", "white marsh", "windsor mill", "woodbine",
    "woodlawn", "baltimore county", "howard county", "anne arundel county",
    "montgomery county", "prince george's county", "frederick county",
    "carroll county", "harford county",
}

# Northern Virginia localities. Central/southern/western VA is out of scope.
VA_CITIES = {
    "alexandria", "annandale", "arlington", "ashburn", "burke", "centreville",
    "chantilly", "dulles", "dumfries", "fairfax", "falls church", "fort belvoir",
    "gainesville", "great falls", "hendon", "herndon", "haymarket", "leesburg",
    "lorton", "manassas", "manassas park", "mclean", "merrifield", "oakton",
    "purcellville", "quantico", "reston", "springfield", "sterling",
    "stafford", "tysons", "tysons corner", "vienna", "warrenton",
    "woodbridge", "fairfax county", "loudoun county", "prince william county",
    "arlington county", "northern virginia",
}

# Anything containing these is rejected even if the state looks right. Guards
# against "Remote - Blacksburg, VA" style strings and far-flung MD towns.
FAR_LOCALITIES = {
    "blacksburg", "charlottesville", "richmond", "roanoke", "salem",
    "norfolk", "virginia beach", "newport news", "chesapeake", "hampton",
    "danville", "lynchburg", "harrisonburg", "staunton", "winchester",
    "williamsburg", "midlothian", "glen allen", "north chesterfield",
    "mount jackson", "nellysford", "altavista", "dayton", "blackstone",
    "cumberland", "oakland", "salisbury", "easton", "elkton", "north east",
    "princess anne", "cambridge", "chestertown", "ocean city", "waldorf md",
    "wilmington", "newark, de", "new castle", "dover", "lewes", "claymont",
    "greenville, de", "windham",
}

REMOTE_PATTERNS = (
    "remote", "work from home", "wfh", "virtual", "telework", "anywhere in the us",
    "us - remote", "united states - remote", "remote - us", "fully remote",
)

# Remote is only accepted if it looks US-scoped (or unqualified).
REMOTE_REJECT_HINTS = (
    "emea", "apac", "canada", "uk only", "united kingdom", "india", "europe",
    "latam", "germany", "ireland", "poland", "singapore", "australia", "japan",
    "china", "brazil", "mexico", "israel",
)

# --------------------------------------------------------------------------
# Role type
# --------------------------------------------------------------------------
# Two buckets are enabled: internships/co-ops, and part-time / research
# assistant roles. Change ENABLED_CATEGORIES to widen or narrow.

ENABLED_CATEGORIES = ("internship", "part_time_research")

INTERNSHIP_PATTERNS = (
    r"\bintern\b", r"\binterns\b", r"\binternship[s]?\b", r"\bco-?op\b",
    r"\bcoop\b", r"\bsummer (?:20\d\d|analyst|associate|scholar|student|program)\b",
    r"\bstudent (?:worker|assistant|researcher|intern|program|trainee)\b",
    r"\bundergraduate\b", r"\bundergrad\b", r"\bcampus\b",
    r"\b(?:university|college) (?:recruiting|program|hire)\b",
    r"\bapprentice(?:ship)?\b", r"\btrainee\b", r"\bpathways\b",
    r"\bsipp\b", r"\bsurf\b", r"\bfellowship\b", r"\bscholar\b",
    r"\bearly (?:career|talent)\b", r"\bpre-?doctoral\b", r"\bpost-?bac\b",
)

PART_TIME_PATTERNS = (
    r"\bpart[- ]time\b", r"\bresearch assistant\b", r"\blab assistant\b",
    r"\blaboratory assistant\b", r"\bresearch aide\b", r"\bstudent aide\b",
    r"\bcontract(?:or)? \(part\b", r"\bhourly\b",
)

# Title contains one of these and no internship signal -> drop. Stops senior
# roles and "Internal Medicine" style false positives leaking in.
SENIORITY_BLOCKLIST = (
    r"\binternal\b", r"\binternist\b", r"\binternational\b",
    r"\bsenior\b", r"\bsr\.?\b", r"\bstaff\b", r"\bprincipal\b", r"\blead\b",
    r"\bdirector\b", r"\bmanager\b", r"\bhead of\b", r"\bvp\b",
    r"\bvice president\b", r"\bchief\b", r"\bexecutive\b", r"\bfellow,? m\.?d\b",
    r"\bpostdoc(?:toral)?\b", r"\bph\.?d\.? (?:scientist|candidate required)\b",
    r"\bii+i?\b", r"\bprofessor\b", r"\bfaculty\b",
)

# --------------------------------------------------------------------------
# Relevance to Paul's major (Biocomputational Engineering)
# --------------------------------------------------------------------------
# Keyword -> weight. A job's relevance score is the sum of weights for every
# distinct keyword found in its title (x2) and description (x1).
# Jobs scoring below MIN_RELEVANCE are dropped entirely.

RELEVANCE_KEYWORDS = {
    # --- AI / ML (highest signal) ---
    "machine learning": 6, "deep learning": 6, "artificial intelligence": 5,
    "neural network": 5, "generative ai": 5, "large language model": 5,
    "llm": 4, "nlp": 4, "natural language processing": 5, "computer vision": 5,
    "pytorch": 5, "tensorflow": 5, "scikit-learn": 4, "hugging face": 4,
    "reinforcement learning": 4, "mlops": 4, "predictive model": 4,
    "ai/ml": 6, " ml ": 3, " ai ": 2,

    # --- Data science / analytics ---
    "data science": 6, "data scientist": 6, "data analyst": 4,
    "data analytics": 4, "data engineer": 4, "biostatistic": 5,
    "statistical model": 4, "statistics": 3, "quantitative": 3,
    "data pipeline": 3, "sql": 2, "pandas": 3, "numpy": 3, "r programming": 2,
    "visualization": 2, "dashboard": 2, "etl": 2,

    # --- Computational bio (the sweet spot) ---
    "bioinformatic": 8, "computational biology": 8, "computational biologist": 8,
    "computational chemistry": 6, "cheminformatic": 6, "systems biology": 5,
    "genomic": 5, "transcriptomic": 5, "proteomic": 4, "single-cell": 4,
    "sequencing analysis": 5, "ngs": 3, "multi-omics": 5, "omics": 4,
    "drug discovery": 4, "molecular modeling": 4, "structural biology": 3,
    "protein structure": 4, "docking": 3, "biological data": 5,
    "clinical data": 3, "real-world data": 3, "digital biomarker": 4,
    "medical imaging": 5, "image analysis": 4, "radiomics": 4,
    "health informatics": 5, "clinical informatics": 5, "bioengineering": 5,
    "biomedical engineering": 5, "biocomputational": 9, "biomedical data": 6,

    # --- Software engineering ---
    "software engineer": 5, "software engineering": 5, "software developer": 5,
    "software development": 4, "backend": 3, "back-end": 3, "full stack": 3,
    "full-stack": 3, "web development": 2, "python": 4, "java": 2,
    "c++": 3, "javascript": 2, "typescript": 2, "golang": 2, "rust": 2,
    "api development": 2, "cloud": 2, "aws": 3, "azure": 2, "kubernetes": 2,
    "docker": 2, "git": 1, "linux": 2, "algorithm": 3, "computer science": 4,
    "programming": 3, "automation": 2, "scientific computing": 5,
    "high performance computing": 4, "hpc": 3, "simulation": 3,
    "modeling and simulation": 4, "embedded": 2, "robotics": 3,

    # --- Adjacent / domain flavor ---
    "computational": 5, "informatics": 4, "engineering": 1,
    "research and development": 1, "laboratory automation": 3,
    "digital health": 4, "medtech": 2, "biotech": 1, "pharmaceutical": 1,
}

MIN_RELEVANCE = 6

# Score at or above this is shown as a "strong match" on the site.
STRONG_RELEVANCE = 16

# Titles that are technical enough to keep even with a thin description.
TITLE_RESCUE_PATTERNS = (
    r"\bsoftware\b", r"\bdata\b", r"\bmachine learning\b", r"\bai\b",
    r"\bml\b", r"\bcomputational\b", r"\bbioinformatic", r"\banalytic",
    r"\bengineering\b", r"\bengineer\b", r"\bcomputer\b", r"\bstatistic",
    r"\binformatics\b", r"\bdeveloper\b", r"\bresearch\b", r"\btechnology\b",
    r"\bdigital\b", r"\bmodeling\b", r"\bimaging\b", r"\bautomation\b",
)

# --------------------------------------------------------------------------
# Crawler behaviour
# --------------------------------------------------------------------------

USER_AGENT = (
    "dmv-internship-radar/1.0 (personal job-search tool; "
    "+https://github.com/)"
)
REQUEST_TIMEOUT = 20
MAX_WORKERS = 12
DISCOVERY_MAX_WORKERS = 16
# Re-run ATS discovery for a company at most this often (days).
DISCOVERY_TTL_DAYS = 7
# A job disappears from the site this many days after it stops being listed.
STALE_AFTER_DAYS = 5
# "NEW" badge window.
NEW_WINDOW_DAYS = 7

CAREERS_PATHS = (
    "/careers", "/careers/", "/jobs", "/jobs/", "/careers/jobs",
    "/about/careers", "/company/careers", "/about-us/careers",
    "/join-us", "/work-with-us", "/careers/open-positions",
    "/opportunities", "/employment", "/careers/openings",
)
