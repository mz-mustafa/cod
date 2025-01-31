from typing import List, Dict, Tuple, Optional
from urllib.parse import urlparse
import requests
from dataclasses import dataclass
from enum import Enum
import re
from requests.exceptions import RequestException

@dataclass
class URLResult:
    requested_url: str
    destination_url: str
    status_code: int
    domain: str
    analytics_source: str
    is_valid: bool
    error_message: str = None

class AnalyticsType(Enum):
    GTM = "gtm"
    ADOBE = "adobe"
    UNKNOWN = "unknown"

class URLProcessor:
    def __init__(self, timeout: int = 30):
        self.timeout = timeout
        self.session = requests.Session()
        # Common HTTP headers to mimic browser
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }

    def process_urls(self, urls: List[str]) -> List[URLResult]:
        """Process a list of URLs and return results for each."""
        results = []
        for url in urls:
            try:
                # Validate URL format
                if not self.validate_url(url):
                    results.append(self._create_result(
                        url,
                        destination_url="",
                        status_code=0,
                        domain="",
                        analytics_source=AnalyticsType.UNKNOWN.value,
                        is_valid=False,
                        error_message="Invalid URL format"
                    ))
                    continue

                # Get domain and check URL status
                domain = self.check_domain(url)
                destination_url, status_code = self.get_url_status(url)

                # Only process further if we got a successful response
                if status_code in [200, 301, 302, 307, 308]:
                    # For MVP, we'll just return UNKNOWN as analytics source
                    # This will be replaced with actual detection logic later
                    analytics_source = self.map_analytics_source("unknown")
                    
                    results.append(self._create_result(
                        url,
                        destination_url=destination_url,
                        status_code=status_code,
                        domain=domain,
                        analytics_source=analytics_source,
                        is_valid=True
                    ))
                else:
                    results.append(self._create_result(
                        url,
                        destination_url=destination_url,
                        status_code=status_code,
                        domain=domain,
                        analytics_source=AnalyticsType.UNKNOWN.value,
                        is_valid=False,
                        error_message=f"HTTP {status_code} response"
                    ))

            except Exception as e:
                results.append(self._create_result(
                    url,
                    destination_url="",
                    status_code=0,
                    domain="",
                    analytics_source=AnalyticsType.UNKNOWN.value,
                    is_valid=False,
                    error_message=str(e)
                ))

        return results

    def validate_url(self, url: str) -> bool:
        """Validate URL format."""
        try:
            result = urlparse(url)
            return all([
            result.scheme,
            result.netloc,
            result.scheme in ['http', 'https']  # Only allow http/https
        ])
        except Exception:
            return False

    def check_domain(self, url: str) -> str:
        """Extract domain from URL, raise exception if invalid."""
        if not self.validate_url(url):
            raise Exception(f"Invalid URL format: {url}")
        parsed = urlparse(url)
        return parsed.netloc.lower()

    def get_url_status(self, url: str) -> Tuple[str, int]:
        """
        Make request to URL and handle redirects.
        Returns tuple of (final_url, status_code)
        """
        try:
            response = self.session.get(
                url,
                headers=self.headers,
                timeout=self.timeout,
                allow_redirects=False  # Changed to False to catch redirect status
            )
            final_url = response.url.rstrip('/')
            return final_url, response.status_code
        except RequestException as e:
            raise Exception(f"Request failed: {str(e)}")

    def map_analytics_source(self, source_type: str) -> str:
        """Map analytics source type to standardized identifier."""
        mappings = {
            'gtm': AnalyticsType.GTM.value,
            'adobe': AnalyticsType.ADOBE.value
        }
        return mappings.get(source_type.lower(), AnalyticsType.UNKNOWN.value)

    def is_same_domain(self, url1: str, url2: str) -> bool:
        """Check if two URLs belong to the same domain."""
        try:
            domain1 = self.check_domain(url1)
            domain2 = self.check_domain(url2)
            return domain1 == domain2
        except Exception:
            return False

    def _handle_redirect(self, response: requests.Response) -> Tuple[str, int]:
        """Handle URL redirects and return final destination."""
        return response.url, response.status_code

    def _create_result(self, original_url: str, **kwargs) -> URLResult:
        """Create standardized result object for a processed URL."""
        return URLResult(
            requested_url=original_url,
            destination_url=kwargs.get('destination_url', ''),
            status_code=kwargs.get('status_code', 0),
            domain=kwargs.get('domain', ''),
            analytics_source=kwargs.get('analytics_source', AnalyticsType.UNKNOWN.value),
            is_valid=kwargs.get('is_valid', False),
            error_message=kwargs.get('error_message')
        )

    def __del__(self):
        """Cleanup method to close the session."""
        self.session.close()