"""
EDGAR Form D Lead Finder
-------------------------
Finds startups that recently filed SEC Form D (private capital raise
disclosure), filtered by state and industry keyword.

This is a free, public-data tool. It does NOT scrape personal emails or
phone numbers. It surfaces the company name, filing date, and the named
executives/related persons who SIGNED the public filing (legally required
disclosure), plus a direct link to the filing itself on sec.gov. You take
it from there: look up that named person on LinkedIn, the company site, or
wherever they've made themselves reachable.

Setup (one time):
    pip install edgartools

Usage:
    python edgar_lead_finder.py --state Texas --keyword energy --start-date 2026-01-01 --end-date 2026-06-01
    python edgar_lead_finder.py --state California "New York" Massachusetts Texas Colorado Washington --keyword "climate tech" --start-date 2026-01-01 --end-date 2026-06-01 --limit 100

Notes:
- SEC EDGAR is a free, public US government database. No API key required.
- The library identifies itself to SEC's servers per their usage policy —
  edit IDENTITY_EMAIL below to your real contact info before running, since
  SEC asks for this (it's not optional, it's how they let you in politely).
- "state" filters by the issuer's principal office state, not the founder's
  personal location.
- "keyword" is matched against the company name and industry description.
  Form D's industry field is broad (e.g. "Other Energy"), so a keyword like
  "energy" or "climate" is more reliable than a narrow SIC code.
"""

import argparse
from edgar import search_filings, set_identity

IDENTITY_EMAIL = "Lead Research your_email_here@example.com"  # <-- replace with your real name/email LOCALLY only. Do not commit your real email to a public repo.


def _search_one_state(state: str, keyword: str, start_date: str, end_date: str, limit: int):
    """Runs one server-side search for a single state and returns parsed,
    fund-filtered results (this is the original single-state logic)."""
    query = f"{state} {keyword}"
    print(f"  Searching '{query}'...")

    search_results = search_filings(
        query,
        forms="D",
        start_date=start_date,
        end_date=end_date,
        limit=limit,
    )
    print(f"    -> {len(search_results)} raw results")

    results = []
    excluded_fund_count = 0
    fund_indicators = [
        " lp", " l.p.", "fund", "partners", "capital partners",
        "private capital", "investment fund",
    ]

    for r in search_results:
        try:
            filing = r.get_filing()
            data = filing.obj()

            company_lower = (filing.company or "").lower()
            # Skip investment funds / PE/LP vehicles — these raise capital to
            # invest in OTHER companies, they are not operating startups
            # looking for product funding (the Cephyron-relevant kind).
            if any(indicator in company_lower for indicator in fund_indicators):
                excluded_fund_count += 1
                continue

            related_persons = getattr(data, "related_persons", []) or []
            names = [
                f"{getattr(p, 'first_name', '') or ''} {getattr(p, 'last_name', '') or ''}".strip()
                for p in related_persons
            ]
            names = [n for n in names if n]  # drop any empty strings

            results.append(
                {
                    "company": filing.company,
                    "filing_date": filing.filing_date,
                    "named_executives": names or ["(not parsed — open filing link)"],
                    "filing_link": filing.filing_url,
                    "matched_state": state,
                }
            )
        except Exception:
            # Some filings are malformed or use older schemas — skip, don't crash.
            continue

    if excluded_fund_count:
        print(f"    (filtered out {excluded_fund_count} fund/LP-style filings)")

    return results


def find_form_d_leads(states, keyword: str, start_date: str, end_date: str, limit: int = 25):
    """
    Runs one server-side search per state (since EDGAR's search doesn't
    support multi-state queries directly), then combines and de-duplicates
    results by company name across all states searched.
    """
    set_identity(IDENTITY_EMAIL)

    print(f"Searching Form D filings across {len(states)} state(s) between {start_date} and {end_date}...\n")

    all_results = []
    for state in states:
        state_results = _search_one_state(state, keyword, start_date, end_date, limit)
        all_results.extend(state_results)

    # De-duplicate by company name (same company can surface in more than
    # one state search if e.g. it mentions multiple locations in its filing)
    seen_companies = set()
    deduped = []
    for r in all_results:
        key = r["company"].strip().lower() if r["company"] else ""
        if key and key not in seen_companies:
            seen_companies.add(key)
            deduped.append(r)

    duplicates_removed = len(all_results) - len(deduped)
    if duplicates_removed:
        print(f"\n(Removed {duplicates_removed} duplicate company entries across states.)")

    return deduped


def print_results(results):
    if not results:
        print("\nNo matching filings found. Try a broader keyword or wider date range.")
        return

    print(f"\nFound {len(results)} matching filings:\n")
    for i, r in enumerate(results, 1):
        print(f"{i}. {r['company']}  [{r['matched_state']}]")
        print(f"   Filed: {r['filing_date']}")
        print(f"   Named on filing: {', '.join(r['named_executives'])}")
        print(f"   Filing link: {r['filing_link']}")
        print()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Find recent SEC Form D filings across one or more states and a keyword (fast, server-side search).")
    parser.add_argument("--state", required=True, nargs="+", help="One or more state names, e.g. --state Texas California \"New York\"")
    parser.add_argument("--keyword", required=True, help="Keyword to search for, e.g. energy")
    parser.add_argument("--start-date", required=True, help="Start date, format YYYY-MM-DD")
    parser.add_argument("--end-date", required=True, help="End date, format YYYY-MM-DD")
    parser.add_argument("--limit", type=int, default=25, help="Max results PER STATE (SEC caps this around 100)")
    args = parser.parse_args()

    results = find_form_d_leads(
        states=args.state,
        keyword=args.keyword,
        start_date=args.start_date,
        end_date=args.end_date,
        limit=args.limit,
    )
    print_results(results)
