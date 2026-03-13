import time
import httpx
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from bs4 import BeautifulSoup
from app.scrapers.base import BaseScraper, ScraperUnavailableError, LicenseNotFoundError

SEARCH_URL = "https://www.cslb.ca.gov/OnlineServices/CheckLicenseII/CheckLicense.aspx"
DETAIL_URL = "https://www.cslb.ca.gov/OnlineServices/CheckLicenseII/LicenseDetail.aspx"
SOURCE_URL = "https://www.cslb.ca.gov/"

PT = ZoneInfo("America/Los_Angeles")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; LicenseVerifier/1.0)",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


def _is_maintenance_window() -> bool:
    now_pt = datetime.now(tz=PT)
    # Sunday (6) 8pm to Monday (0) 6am
    weekday = now_pt.weekday()  # Monday=0, Sunday=6
    hour = now_pt.hour
    if weekday == 6 and hour >= 20:
        return True
    if weekday == 0 and hour < 6:
        return True
    return False


def _get_viewstate(soup: BeautifulSoup) -> dict:
    fields = {}
    for name in ["__VIEWSTATE", "__VIEWSTATEGENERATOR", "__EVENTVALIDATION"]:
        tag = soup.find("input", {"name": name})
        if tag:
            fields[name] = tag.get("value", "")
    return fields


class CAScraper(BaseScraper):
    state_code = "CA"

    def _get(self, url: str, params=None, retries: int = 2) -> httpx.Response:
        for attempt in range(retries + 1):
            try:
                with httpx.Client(timeout=10.0, follow_redirects=True) as client:
                    resp = client.get(url, params=params, headers=HEADERS)
                    resp.raise_for_status()
                    return resp
            except httpx.HTTPError as e:
                if attempt == retries:
                    raise ScraperUnavailableError(f"CSLB request failed: {e}") from e
                time.sleep(1)

    def _post(self, url: str, data: dict, retries: int = 2) -> httpx.Response:
        for attempt in range(retries + 1):
            try:
                with httpx.Client(timeout=10.0, follow_redirects=True) as client:
                    resp = client.post(url, data=data, headers=HEADERS)
                    resp.raise_for_status()
                    return resp
            except httpx.HTTPError as e:
                if attempt == retries:
                    raise ScraperUnavailableError(f"CSLB request failed: {e}") from e
                time.sleep(1)

    def verify(self, license_number: str) -> dict:
        if _is_maintenance_window():
            raise ScraperUnavailableError(
                "CSLB offline for maintenance (Sundays 8pm – Mondays 6am PT)"
            )

        # Step 1: Load the search page to get ASP.NET form state
        resp = self._get(SEARCH_URL)
        soup = BeautifulSoup(resp.text, "html.parser")
        viewstate = _get_viewstate(soup)

        # Step 2: Submit the form with license number
        post_data = {
            **viewstate,
            "__EVENTTARGET": "",
            "__EVENTARGUMENT": "",
            "ctl00$MainContent$RadioButtonList1": "0",  # search by license number
            "ctl00$MainContent$txtLicenseNumber": license_number,
            "ctl00$MainContent$btnSearch": "Search",
        }
        time.sleep(1)
        resp2 = self._post(SEARCH_URL, post_data)
        soup2 = BeautifulSoup(resp2.text, "html.parser")

        return self._parse_verify_response(soup2, license_number)

    def _parse_verify_response(self, soup: BeautifulSoup, license_number: str) -> dict:
        # Check for "no results" indicators
        no_results = soup.find(string=lambda t: t and "no license" in t.lower())
        if no_results:
            raise LicenseNotFoundError(f"No CA license found for {license_number}")

        # Look for license detail table
        detail_table = soup.find("table", {"id": lambda x: x and "Grid" in str(x)})
        if not detail_table:
            # Try any data table
            tables = soup.find_all("table")
            detail_table = next(
                (t for t in tables if t.find("td") and len(t.find_all("tr")) > 1),
                None,
            )

        if not detail_table:
            raise LicenseNotFoundError(f"No CA license found for {license_number}")

        data = {}
        rows = detail_table.find_all("tr")
        for row in rows:
            cells = row.find_all(["td", "th"])
            if len(cells) >= 2:
                label = cells[0].get_text(strip=True).lower()
                value = cells[1].get_text(strip=True)
                if "license number" in label or "lic #" in label:
                    data["license_number"] = value
                elif "status" in label:
                    data["status"] = value
                elif "expir" in label:
                    data["expiration_date"] = value
                elif "license type" in label or "type" in label:
                    data["license_type"] = value
                elif "business name" in label or "company" in label:
                    data["business_name"] = value
                elif "owner" in label or "personnel" in label:
                    data["owner_name"] = value
                elif "address" in label:
                    data["address"] = value

        # Check if we actually got useful data
        if not data:
            raise LicenseNotFoundError(f"No CA license found for {license_number}")

        # Disciplinary actions / complaints
        complaints = []
        complaint_section = soup.find(string=lambda t: t and "complaint" in t.lower())
        if complaint_section:
            parent = complaint_section.find_parent()
            if parent:
                complaint_text = parent.get_text(strip=True)
                if "no complaint" not in complaint_text.lower() and complaint_text:
                    complaints.append(complaint_text)

        return {
            "license_number": data.get("license_number", license_number),
            "state": "CA",
            "status": data.get("status"),
            "expiration_date": data.get("expiration_date"),
            "license_type": data.get("license_type"),
            "business_name": data.get("business_name"),
            "owner_name": data.get("owner_name"),
            "address": data.get("address"),
            "disciplinary_actions": complaints,
            "verified_at": datetime.now(tz=timezone.utc).isoformat(),
            "source_url": DETAIL_URL,
            "cache_hit": False,
        }

    def search(self, name: str, limit: int = 10) -> list:
        if _is_maintenance_window():
            raise ScraperUnavailableError(
                "CSLB offline for maintenance (Sundays 8pm – Mondays 6am PT)"
            )

        resp = self._get(SEARCH_URL)
        soup = BeautifulSoup(resp.text, "html.parser")
        viewstate = _get_viewstate(soup)

        # Split name for first/last if possible
        parts = name.strip().split()
        last_name = parts[0] if parts else name
        first_name = parts[1] if len(parts) > 1 else ""

        post_data = {
            **viewstate,
            "__EVENTTARGET": "",
            "__EVENTARGUMENT": "",
            "ctl00$MainContent$RadioButtonList1": "1",  # search by business name
            "ctl00$MainContent$txtBusinessName": name,
            "ctl00$MainContent$btnSearch": "Search",
        }
        time.sleep(1)
        resp2 = self._post(SEARCH_URL, post_data)
        soup2 = BeautifulSoup(resp2.text, "html.parser")

        return self._parse_search_response(soup2, limit)

    def _parse_search_response(self, soup: BeautifulSoup, limit: int) -> list:
        results = []
        tables = soup.find_all("table")
        for table in tables:
            rows = table.find_all("tr")
            if len(rows) < 2:
                continue
            header_cells = [td.get_text(strip=True).lower() for td in rows[0].find_all(["th", "td"])]
            if not any("license" in h or "status" in h or "name" in h for h in header_cells):
                continue
            for row in rows[1:]:
                cells = row.find_all("td")
                if len(cells) < 2:
                    continue
                item = {}
                for i, cell in enumerate(cells):
                    if i < len(header_cells):
                        label = header_cells[i]
                        val = cell.get_text(strip=True)
                        if "license" in label and "#" in label or label == "license number":
                            item["license_number"] = val
                        elif "business" in label or "name" in label:
                            item["business_name"] = val
                        elif "status" in label:
                            item["status"] = val
                        elif "type" in label:
                            item["license_type"] = val
                        elif "expir" in label:
                            item["expiration_date"] = val
                if "license_number" in item:
                    results.append(item)
                if len(results) >= limit:
                    break
        return results

    def health_check(self) -> bool:
        if _is_maintenance_window():
            return False
        try:
            resp = self._get(SEARCH_URL)
            return resp.status_code == 200
        except ScraperUnavailableError:
            return False
