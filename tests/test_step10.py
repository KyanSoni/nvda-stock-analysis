"""Step 10 offline tests: the README's links resolve, its call matches the memo's first line, and the public-facing
documents contain no e-mail address. Runs on the committed files only."""
import re

from common import PROJECT_ROOT

README = PROJECT_ROOT / "README.md"
MEMO = PROJECT_ROOT / "docs" / "memo" / "NVDA_investment_memo.md"
PREP = PROJECT_ROOT / "docs" / "interview_prep.md"


def test_readme_relative_links_exist():
    text = README.read_text(encoding="utf-8")
    links = [l for l in re.findall(r"\]\(([^)#\s]+)\)", text) if not l.startswith(("http://", "https://", "mailto:"))]
    assert links, "README has no relative links"
    missing = [l for l in links if not (PROJECT_ROOT / l).exists()]
    assert not missing, f"README links to missing files: {missing}"


def test_readme_call_matches_memo():
    first = MEMO.read_text(encoding="utf-8").splitlines()[0]
    m = re.match(r"# NVIDIA \(NVDA\): (Buy|Hold|Sell), 12-month target \$([\d,]+)", first)
    assert m, first
    title = README.read_text(encoding="utf-8").splitlines()[0]
    assert title == f"# NVIDIA (NVDA): {m.group(1)}, 12-month target ${m.group(2)}", (title, first)


def test_no_email_addresses_in_public_documents():
    pat = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
    for p in (README, PREP, MEMO):
        found = [e for e in pat.findall(p.read_text(encoding="utf-8")) if not e.endswith("@example.com")]
        assert not found, f"{p.name}: {found}"
