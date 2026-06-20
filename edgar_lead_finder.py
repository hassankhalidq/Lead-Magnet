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
from edgar import get_filings, set_identity

IDENTITY_EMAIL = "Hassan H research@example.com"  # <-- put your real name/email here


def find_form_d_leads(state: str, keyword: str, years, quarters, limit: int = 25):
    set_identity(IDENTITY_EMAIL)

    print(f"Fetching Form D filings for {years} Q{quarters}...")
    filings = get_filings(year=years, quarter=quarters, form="D")
    print(f"Total Form D filings in this period: {len(filings)}")

    results = []
    keyword_lower = keyword.lower()

    for filing in filings:
        try:
            company_name = filing.company or ""
            if keyword_lower not in company_name.lower():
                # quick pre-filter on name; full check happens via parsed data below
                pass

            data = filing.obj()  # parsed Form D structured data
            if data is None:
                continue

            issuer_state = getattr(data, "issuer_state", None) or getattr(
                data, "state_of_incorporation", None
            )
            industry = str(getattr(data, "industry_group", "")) or ""

            state_match = issuer_state and state.upper() in str(issuer_state).upper()
            keyword_match = (
                keyword_lower in company_name.lower()
                or keyword_lower in industry.lower()
            )

            if state_match and keyword_match:
                related_persons = getattr(data, "related_persons", []) or []
                names = [
                    f"{p.get('first_name', '')} {p.get('last_name', '')}".strip()
                    for p in related_persons
                    if isinstance(p, dict)
                ]

                results.append(
                    {
                        "company": company_name,
                        "filing_date": filing.filing_date,
                        "named_executives": names or ["(not parsed — open filing link)"],
                        "industry": industry,
                        "filing_link": filing.filing_url,
                    }
                )

                if len(results) >= limit:
                    break

        except Exception:
            # Some Form D filings are malformed or use older schemas.
            # Skip silently rather than crash the whole run.
            continue

    return results


def print_results(results):
    if not results:
        print("\nNo matching filings found. Try a broader keyword or different quarter.")
        return

    print(f"\nFound {len(results)} matching filings:\n")
    for i, r in enumerate(results, 1):
        print(f"{i}. {r['company']}")
        print(f"   Filed: {r['filing_date']}")
        print(f"   Industry: {r['industry']}")
        print(f"   Named on filing: {', '.join(r['named_executives'])}")
        print(f"   Filing link: {r['filing_link']}")
        print()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Find recent SEC Form D filings by state and keyword.")
    parser.add_argument("--state", required=True, help="Two-letter state code, e.g. TX")
    parser.add_argument("--keyword", required=True, help="Keyword to match in company name/industry, e.g. energy")
    parser.add_argument("--year", type=int, required=True, help="Calendar year, e.g. 2026")
    parser.add_argument("--quarter", type=int, nargs="+", required=True, help="Quarter(s), e.g. 1 2")
    parser.add_argument("--limit", type=int, default=25, help="Max results to return")
    args = parser.parse_args()

    results = find_form_d_leads(
        state=args.state,
        keyword=args.keyword,
        years=args.year,
        quarters=args.quarter,
        limit=args.limit,
    )
    print_results(results)
