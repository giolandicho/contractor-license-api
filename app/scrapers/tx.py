import time
import httpx
from datetime import datetime, timezone
from bs4 import BeautifulSoup
from app.scrapers.base import BaseScraper, ScraperUnavailableError, LicenseNotFoundError, normalize_date

SEARCH_URL = "https://www.tdlr.texas.gov/LicenseSearch/"
SOURCE_URL = "https://www.tdlr.texas.gov/"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; LicenseVerifier/1.0)",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Referer": SEARCH_URL,
}


class TXScraper(BaseScraper):
    state_code = "TX"

    def _get(self, url: str, params=None, retries: int = 2) -> httpx.Response:
        for attempt in range(retries + 1):
            try:
                with httpx.Client(timeout=httpx.Timeout(connect=5.0, read=15.0), follow_redirects=True) as client:
                    resp = client.get(url, params=params, headers=HEADERS)
                    resp.raise_for_status()
                    return resp
            except httpx.HTTPError as e:
                if attempt == retries:
                    raise ScraperUnavailableError(f"TDLR request failed: {e}") from e
                time.sleep(1)

    def _post(self, url: str, data: dict, retries: int = 2) -> httpx.Response:
        for attempt in range(retries + 1):
            try:
                with httpx.Client(timeout=httpx.Timeout(connect=5.0, read=15.0), follow_redirects=True) as client:
                    resp = client.post(url, data=data, headers=HEADERS)
                    resp.raise_for_status()
                    return resp
            except httpx.HTTPError as e:
                if attempt == retries:
                    raise ScraperUnavailableError(f"TDLR request failed: {e}") from e
                time.sleep(1)

    def _get_form_fields(self, soup: BeautifulSoup) -> dict:
        fields = {}
        for inp in soup.find_all("input", {"type": ["hidden", "text", "radio"]}):
            name = inp.get("name")
            if name:
                fields[name] = inp.get("value", "")
        return fields

    def verify(self, license_number: str) -> dict:
        resp = self._get(SEARCH_URL)
        soup = BeautifulSoup(resp.text, "html.parser")
        form_fields = self._get_form_fields(soup)

        post_data = {
            **form_fields,
            "searchType": "LicenseNumber",
            "licenseNumber": license_number,
            "searchButton": "Search",
        }
        time.sleep(1)
        resp2 = self._post(SEARCH_URL, post_data)
        soup2 = BeautifulSoup(resp2.text, "html.parser")

        return self._parse_verify(soup2, license_number)

    def _parse_verify(self, soup: BeautifulSoup, license_number: str) -> dict:
        # Check for no results
        no_match = soup.find(string=lambda t: t and (
            "no records" in t.lower() or "no results" in t.lower() or "not found" in t.lower()
        ))
        if no_match:
            raise LicenseNotFoundError(f"No TX license found for {license_number}")

        data = {}
        # TDLR detail pages use definition lists or tables
        dl = soup.find("dl")
        if dl:
            terms = dl.find_all("dt")
            descs = dl.find_all("dd")
            for dt, dd in zip(terms, descs):
                label = dt.get_text(strip=True).lower()
                value = dd.get_text(strip=True)
                if "license number" in label or "license #" in label:
                    data["license_number"] = value
                elif "status" in label:
                    data["status"] = value
                elif "expir" in label:
                    data["expiration_date"] = value
                elif "license type" in label or "type" in label:
                    data["license_type"] = value
                elif "name" in label and "business" in label:
                    data["business_name"] = value
                elif "name" in label:
                    data["owner_name"] = value
                elif "address" in label or "city" in label:
                    existing = data.get("address", "")
                    data["address"] = (existing + " " + value).strip()

        # Fallback: look for any table
        if not data:
            tables = soup.find_all("table")
            for table in tables:
                rows = table.find_all("tr")
                for row in rows:
                    cells = row.find_all(["td", "th"])
                    if len(cells) >= 2:
                        label = cells[0].get_text(strip=True).lower()
                        value = cells[1].get_text(strip=True)
                        if "license" in label and ("number" in label or "#" in label):
                            data["license_number"] = value
                        elif "status" in label:
                            data["status"] = value
                        elif "expir" in label:
                            data["expiration_date"] = value
                        elif "type" in label:
                            data["license_type"] = value
                        elif "business" in label or "company" in label:
                            data["business_name"] = value
                        elif "name" in label:
                            data["owner_name"] = value
                        elif "address" in label:
                            data["address"] = value

        if not data:
            raise LicenseNotFoundError(f"No TX license found for {license_number}")

        return {
            "license_number": data.get("license_number", license_number),
            "state": "TX",
            "status": data.get("status"),
            "expiration_date": normalize_date(data.get("expiration_date")),
            "license_type": data.get("license_type"),
            "business_name": data.get("business_name"),
            "owner_name": data.get("owner_name"),
            "address": data.get("address"),
            "disciplinary_actions": None,
            "verified_at": datetime.now(tz=timezone.utc).isoformat(),
            "source_url": SEARCH_URL,
            "cache_hit": False,
        }

    def search(self, name: str, limit: int = 10) -> list:
        resp = self._get(SEARCH_URL)
        soup = BeautifulSoup(resp.text, "html.parser")
        form_fields = self._get_form_fields(soup)

        post_data = {
            **form_fields,
            "searchType": "BusinessName",
            "businessName": name,
            "searchButton": "Search",
        }
        time.sleep(1)
        resp2 = self._post(SEARCH_URL, post_data)
        soup2 = BeautifulSoup(resp2.text, "html.parser")

        return self._parse_search(soup2, limit)

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
                    if "license number" in h or "lic #" in h or h == "license":
                        item["license_number"] = val
                    elif "business" in h or "name" in h:
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
            resp = self._get(SEARCH_URL)
            return resp.status_code == 200
        except ScraperUnavailableError:
            return False
