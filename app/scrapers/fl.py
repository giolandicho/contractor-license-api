import time
import httpx
from datetime import datetime, timezone
from bs4 import BeautifulSoup
from app.scrapers.base import BaseScraper, ScraperUnavailableError, LicenseNotFoundError

SEARCH_URL = "https://www.myfloridalicense.com/wl11.asp"
DETAIL_URL = "https://www.myfloridalicense.com/LicenseDetail.asp"
SOURCE_URL = "https://www.myfloridalicense.com/"

# Construction Industry board codes for DBPR
CONSTRUCTION_BOARDS = ["CBC", "CGC", "CRC", "CCC", "CAC", "CFC", "EC", "CUC", "CMC", "CPC"]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; LicenseVerifier/1.0)",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Referer": SOURCE_URL,
}


class FLScraper(BaseScraper):
    state_code = "FL"

    def _get(self, url: str, params=None, retries: int = 2) -> httpx.Response:
        for attempt in range(retries + 1):
            try:
                with httpx.Client(timeout=10.0, follow_redirects=True) as client:
                    resp = client.get(url, params=params, headers=HEADERS)
                    resp.raise_for_status()
                    return resp
            except httpx.HTTPError as e:
                if attempt == retries:
                    raise ScraperUnavailableError(f"DBPR request failed: {e}") from e
                time.sleep(1)

    def verify(self, license_number: str) -> dict:
        params = {
            "search": "2",
            "LicNbr": license_number,
        }
        time.sleep(1)
        resp = self._get(SEARCH_URL, params=params)
        soup = BeautifulSoup(resp.text, "html.parser")
        return self._parse_verify(soup, license_number)

    def _parse_verify(self, soup: BeautifulSoup, license_number: str) -> dict:
        # Check no results
        no_match = soup.find(string=lambda t: t and (
            "no records" in t.lower()
            or "no license" in t.lower()
            or "not found" in t.lower()
            or "0 records" in t.lower()
        ))
        if no_match:
            raise LicenseNotFoundError(f"No FL license found for {license_number}")

        data = {}

        # DBPR uses tables for license detail
        tables = soup.find_all("table")
        for table in tables:
            rows = table.find_all("tr")
            for row in rows:
                cells = row.find_all(["td", "th"])
                if len(cells) >= 2:
                    label = cells[0].get_text(strip=True).lower()
                    value = cells[1].get_text(strip=True)
                    if "license number" in label or "lic nbr" in label or "lic #" in label:
                        data["license_number"] = value
                    elif "status" in label:
                        data["status"] = value
                    elif "expir" in label:
                        data["expiration_date"] = value
                    elif "license type" in label or "type" in label:
                        data["license_type"] = value
                    elif "name" in label and ("business" in label or "licensee" in label or "dba" in label):
                        data["business_name"] = value
                    elif "name" in label and not data.get("owner_name"):
                        data["owner_name"] = value
                    elif "address" in label:
                        existing = data.get("address", "")
                        data["address"] = (existing + " " + value).strip() if existing else value
                    elif "city" in label:
                        data["address"] = (data.get("address", "") + ", " + value).lstrip(", ")
                    elif "county" in label:
                        pass  # skip county
                    elif "state" in label and len(value) == 2:
                        data["address"] = (data.get("address", "") + ", " + value).lstrip(", ")

        if not data:
            raise LicenseNotFoundError(f"No FL license found for {license_number}")

        # Check for disciplinary actions
        disciplinary = []
        disc_section = soup.find(string=lambda t: t and "disciplinary" in t.lower())
        if disc_section:
            parent = disc_section.find_parent()
            if parent:
                # Walk sibling elements to find discipline text
                for sib in parent.find_next_siblings():
                    text = sib.get_text(strip=True)
                    if text and len(text) > 10:
                        disciplinary.append(text)
                        break

        return {
            "license_number": data.get("license_number", license_number),
            "state": "FL",
            "status": data.get("status"),
            "expiration_date": data.get("expiration_date"),
            "license_type": data.get("license_type"),
            "business_name": data.get("business_name"),
            "owner_name": data.get("owner_name"),
            "address": data.get("address"),
            "disciplinary_actions": disciplinary,
            "verified_at": datetime.now(tz=timezone.utc).isoformat(),
            "source_url": DETAIL_URL,
            "cache_hit": False,
        }

    def search(self, name: str, limit: int = 10) -> list:
        parts = name.strip().split()
        first_name = parts[0] if parts else ""
        last_name = parts[1] if len(parts) > 1 else ""

        params = {
            "search": "1",
            "FirstName": first_name,
            "LastName": last_name,
        }
        time.sleep(1)
        resp = self._get(SEARCH_URL, params=params)
        soup = BeautifulSoup(resp.text, "html.parser")
        return self._parse_search(soup, limit)

    def _parse_search(self, soup: BeautifulSoup, limit: int) -> list:
        results = []
        tables = soup.find_all("table")
        for table in tables:
            rows = table.find_all("tr")
            if len(rows) < 2:
                continue
            headers = [td.get_text(strip=True).lower() for td in rows[0].find_all(["th", "td"])]
            if not any("license" in h or "name" in h for h in headers):
                continue
            for row in rows[1:]:
                cells = row.find_all("td")
                if not cells:
                    continue
                item = {}
                for i, cell in enumerate(cells):
                    if i >= len(headers):
                        break
                    h = headers[i]
                    val = cell.get_text(strip=True)
                    if "license number" in h or "lic nbr" in h or h == "license":
                        item["license_number"] = val
                    elif "business" in h or "licensee" in h or "name" in h:
                        item["business_name"] = val
                    elif "status" in h:
                        item["status"] = val
                    elif "type" in h:
                        item["license_type"] = val
                    elif "expir" in h:
                        item["expiration_date"] = val
                if "license_number" in item:
                    results.append(item)
                if len(results) >= limit:
                    break
        return results

    def health_check(self) -> bool:
        try:
            resp = self._get(SOURCE_URL)
            return resp.status_code == 200
        except ScraperUnavailableError:
            return False
