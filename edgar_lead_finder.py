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
    python edgar_lead_finder.py --state TX --keyword energy --year 2026 --quarter 1 2
    python edgar_lead_finder.py --state TX --keyword climate --year 2026 --quarter 2

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


def find_form_d_leads(state: str, keyword: str, start_date: str, end_date: str, limit: int = 25):
    """
    Uses SEC EDGAR's full-text search (server-side), so we only download
    filings that already match — not all Form D filings in the period.
    This is dramatically faster than looping through every Form D filing.
    """
    set_identity(IDENTITY_EMAIL)

    query = f"{state} {keyword}"
    print(f"Searching Form D filings for '{query}' between {start_date} and {end_date}...")

    search_results = search_filings(
        query,
        forms="D",
        start_date=start_date,
        end_date=end_date,
        limit=limit,
    )
    print(f"Search returned {len(search_results)} results.")

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
                }
            )
        except Exception:
            # Some filings are malformed or use older schemas — skip, don't crash.
            continue

    if excluded_fund_count:
        print(f"(Filtered out {excluded_fund_count} investment fund/LP-style filings by name pattern — these raise capital to invest elsewhere, not operating startups.)")

    return results


def print_results(results):
    if not results:
        print("\nNo matching filings found. Try a broader keyword or wider date range.")
        return

    print(f"\nFound {len(results)} matching filings:\n")
    for i, r in enumerate(results, 1):
        print(f"{i}. {r['company']}")
        print(f"   Filed: {r['filing_date']}")
        print(f"   Named on filing: {', '.join(r['named_executives'])}")
        print(f"   Filing link: {r['filing_link']}")
        print()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Find recent SEC Form D filings by state and keyword (fast, server-side search).")
    parser.add_argument("--state", required=True, help="State name or abbreviation to search for, e.g. Texas")
    parser.add_argument("--keyword", required=True, help="Keyword to search for, e.g. energy")
    parser.add_argument("--start-date", required=True, help="Start date, format YYYY-MM-DD")
    parser.add_argument("--end-date", required=True, help="End date, format YYYY-MM-DD")
    parser.add_argument("--limit", type=int, default=25, help="Max results to return (max 100)")
    args = parser.parse_args()

    results = find_form_d_leads(
        state=args.state,
        keyword=args.keyword,
        start_date=args.start_date,
        end_date=args.end_date,
        limit=args.limit,
    )
    print_results(results)
