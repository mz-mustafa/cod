from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Dict, Optional, Pattern
import re

@dataclass
class CookieProviderSignature:
    """Base signature structure for cookie consent providers"""
    banner_ids: List[str]             # HTML IDs to identify the banner
    reject_button_ids: List[str]      # HTML IDs for reject buttons
    accept_button_ids: List[str]      # HTML IDs for accept buttons
    manage_button_ids: List[str]      # HTML IDs for manage/settings buttons
    provider_name: str                # Name of the provider
    provider_base_domain: str         # Base domain of the provider 

@dataclass
class AnalyticsProviderSignature:
    """Signature structure for analytics providers"""
    provider_name: str                # Name of the analytics provider
    container_domains: List[str]        # Base domains for container loading
    container_url_patterns: List[str]   # URL patterns to match container loads
    event_domains: List[str]          # Base domains for analytics events
    event_url_patterns: List[str]     # URL patterns to match analytics events (not containers)

class TrustArcSignature(CookieProviderSignature):
    """TrustArc specific signature implementation"""
    def __init__(self):
        super().__init__(
            banner_ids=[
                "truste-consent-track",
                "truste-consent-button",
                "truste-cookie-button"
            ],
            reject_button_ids=[
                "reject-all-cookies",
                "truste-cookie-reject",
                "truste-consent-required"
            ],
            accept_button_ids=[
                "truste-consent-button",
                "truste-cookie-accept",
                "truste-consent-button"
            ],
            manage_button_ids=[
                "truste-show-options",
                "truste-cookie-preferences",
                "truste-show-consent"
            ],
            provider_name="TrustArc",
            provider_base_domain="trustarc.com"

        )

class OneTrustSignature(CookieProviderSignature):
    """OneTrust specific signature implementation"""
    def __init__(self):
        super().__init__(
            banner_ids=[
                "onetrust-banner-sdk",
                "onetrust-consent-sdk"
            ],
            reject_button_ids=[
                "onetrust-reject-all-handler",
                "reject-all-cookies-button"
            ],
            accept_button_ids=[
                "onetrust-accept-btn-handler",
                "accept-all-cookies-button"
            ],
            manage_button_ids=[
                "onetrust-pc-btn-handler",
                "cookie-settings-button"
            ],
            provider_name="OneTrust",
            provider_base_domain="cookielaw.org"
        )

class GoogleAnalyticsSignature(AnalyticsProviderSignature):
    """Google Analytics (GA4) signature implementation"""
    def __init__(self):
        super().__init__(
            provider_name="Google Analytics",
            container_domains=["google-analytics.com", "googletagmanager.com"],
            container_url_patterns=[
                r"google-analytics\.com\/analytics\.js$",
                r"googletagmanager\.com\/gtag\/js",
                r"googletagmanager\.com\/gtm\.js"
            ],
            event_domains=["google-analytics.com", "googletagmanager.com"],
            event_url_patterns=[
                r"google-analytics\.com\/collect",
                r"google-analytics\.com\/j\/collect",
                r"google-analytics\.com\/r\/collect",
                r"google-analytics\.com\/g\/collect",
                r"stats\.g\.doubleclick\.net"
            ]
        )

class AdobeAnalyticsSignature(AnalyticsProviderSignature):
    """Adobe Analytics signature implementation"""
    def __init__(self):
        super().__init__(
            provider_name="Adobe Analytics",
            container_domains=["adobetc.com", "adobedtm.com", "omtrdc.net"],
            container_url_patterns=[
                r"assets\.adobetc\.com\/.*\.js$",
                r"assets\.adobedtm\.com\/.*\.js$",
                r"launch-.*\.adobedtm\.com.*\.js$"
            ],
            event_domains=["omtrdc.net", "2o7.net", "adobedc.net"],
            event_url_patterns=[
                r"\.112\.2o7\.net",
                r"\.sc\.omtrdc\.net\/b\/ss",
                r"\.demdex\.net\/id",
                r"dpm\.demdex\.net"
            ]
        )

class UsercentricsSignature(CookieProviderSignature):
    """Usercentrics/Cookiebot specific signature implementation"""
    def __init__(self):
        super().__init__(
            banner_ids=[
                "CybotCookiebotDialog"
            ],
            reject_button_ids=[
                "CybotCookiebotDialogBodyButtonDecline"
            ],
            accept_button_ids=[
                "CybotCookiebotDialogBodyLevelButtonLevelOptinAllowAll"
            ],
            manage_button_ids=[
                "CybotCookiebotDialogBodyLevelButtonLevelOptinAllowallSelection"
            ],
            provider_name="Usercentrics/Cookiebot",
            provider_base_domain="cookiebot.com"
        )

class ProviderRegistry:
    """Registry managing cookie consent provider signatures"""
    
    def __init__(self):
        self._providers: Dict[str, CookieProviderSignature] = {
            "trustarc": TrustArcSignature(),
            "onetrust": OneTrustSignature(),
            "usercentrics": UsercentricsSignature()
        }
        self._analytics_providers: Dict[str, AnalyticsProviderSignature] = {
            "google_analytics": GoogleAnalyticsSignature(),
            "adobe_analytics": AdobeAnalyticsSignature()
        }
    
    def get_provider(self, page_content: str) -> Optional[CookieProviderSignature]:
        """
        Identify provider from page content primarily using banner IDs, which are 
        designed to be unique identifiers for each provider.
        Returns None if no known provider is detected
        """
        page_content = page_content.lower()
        
        for provider_name, signature in self._providers.items():
            # Check for any of the banner IDs in content - this is sufficient for identification
            banner_match = any(
                banner_id.lower() in page_content 
                for banner_id in signature.banner_ids
            )
            
            # Banner ID match is sufficient for identification
            if banner_match:
                return signature
                
        return None
    
    def is_analytics_container_load(self, url: str, domain: str) -> Dict[str, bool]:
        """
        Check if a URL matches known analytics container load patterns.
        
        Args:
            url: URL to check
            domain: Domain of the URL
            
        Returns:
            Dictionary with provider names as keys and boolean match results
        """
        results = {}
        for provider_key, provider in self._analytics_providers.items():
            # First check if the domain is in container domains
            if any(container_domain in domain for container_domain in provider.container_domains):
                # Then check if URL matches any container pattern (not event pattern)
                is_container = any(re.search(pattern, url) for pattern in provider.container_url_patterns)
                # Check that it's not an event URL pattern
                is_not_event = not any(re.search(pattern, url) for pattern in provider.event_url_patterns)
                
                results[provider_key] = is_container and is_not_event
            else:
                results[provider_key] = False
            
        return results
    
    def is_analytics_event(self, url: str, domain: str) -> Dict[str, bool]:
        """
        Check if a URL matches known analytics event patterns.
        
        Args:
            url: URL to check
            domain: Domain of the URL
            
        Returns:
            Dictionary with provider names as keys and boolean match results
        """
        results = {}
        for provider_key, provider in self._analytics_providers.items():
            # First check if the domain is in event domains
            if any(event_domain in domain for event_domain in provider.event_domains):
                # Then check if URL matches any event pattern
                is_event = any(re.search(pattern, url) for pattern in provider.event_url_patterns)
                
                results[provider_key] = is_event
            else:
                results[provider_key] = False
            
        return results
    
    def get_analytics_provider_by_domain(self, domain: str) -> Optional[AnalyticsProviderSignature]:
        """
        Check if a domain matches known analytics provider domains.
        
        Args:
            domain: Domain to check
            
        Returns:
            The matching analytics provider signature or None
        """
        for provider in self._analytics_providers.values():
            # Check container domains
            if any(container_domain in domain for container_domain in provider.container_domains):
                return provider
            # Check event domains
            if any(event_domain in domain for event_domain in provider.event_domains):
                return provider
                
        return None
    
    def add_provider(self, key: str, signature: CookieProviderSignature) -> None:
        """Register a new provider signature"""
        self._providers[key.lower()] = signature
    
    def add_analytics_provider(self, key: str, signature: AnalyticsProviderSignature) -> None:
        """Register a new analytics provider signature"""
        self._analytics_providers[key.lower()] = signature
    
    def get_all_providers(self) -> Dict[str, CookieProviderSignature]:
        """Get all registered providers"""
        return self._providers.copy()
    
    def get_all_analytics_providers(self) -> Dict[str, AnalyticsProviderSignature]:
        """Get all registered analytics providers"""
        return self._analytics_providers.copy()