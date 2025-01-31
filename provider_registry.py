from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Dict, Optional

@dataclass
class CookieProviderSignature:
    """Base signature structure for cookie consent providers"""
    banner_ids: List[str]             # HTML IDs to identify the banner
    reject_button_ids: List[str]      # HTML IDs for reject buttons
    accept_button_ids: List[str]      # HTML IDs for accept buttons
    manage_button_ids: List[str]      # HTML IDs for manage/settings buttons
    provider_name: str                # Name of the provider

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
            provider_name="TrustArc"
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
            provider_name="OneTrust"
        )

class ProviderRegistry:
    """Registry managing cookie consent provider signatures"""
    
    def __init__(self):
        self._providers: Dict[str, CookieProviderSignature] = {
            "trustarc": TrustArcSignature(),
            "onetrust": OneTrustSignature()
        }
    
    def get_provider(self, page_content: str) -> Optional[CookieProviderSignature]:
        """
        Identify provider from page content. Checks both provider name and banner IDs
        to ensure accurate detection.
        Returns None if no known provider is detected
        """
        page_content = page_content.lower()
        
        for provider_name, signature in self._providers.items():
            # Check for provider name in content
            name_match = provider_name.lower() in page_content
            
            # Check for any of the banner IDs in content
            banner_match = any(
                banner_id.lower() in page_content 
                for banner_id in signature.banner_ids
            )
            
            # Only return if both name and at least one banner ID is found
            if name_match and banner_match:
                return signature
                
        return None
    
    def add_provider(self, key: str, signature: CookieProviderSignature) -> None:
        """Register a new provider signature"""
        self._providers[key.lower()] = signature
    
    def get_all_providers(self) -> Dict[str, CookieProviderSignature]:
        """Get all registered providers"""
        return self._providers.copy()