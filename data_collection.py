from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
from url_processor import URLResult
from browser_manager import BrowserManager, BrowserState, NetworkRequest
from provider_registry import CookieProviderSignature
import time
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

class CookieAnalysisKeys:
    """Constants for cookie analysis to avoid string repetition and typos"""
    # Cookie metrics
    FIRST_PARTY_COOKIES = 'firstPartyCookies'
    CCM_PROVIDER_COOKIES = 'ccmProviderCookies'
    NO_THIRD_PARTY_COOKIES = 'noThirdPartyCookies'
    
    # Request metrics
    FIRST_PARTY_REQUESTS = 'firstPartyRequests'
    CCM_PROVIDER_REQUESTS = 'ccmProviderRequests'
    NO_THIRD_PARTY_REQUESTS = 'noThirdPartyRequests'
    
    # Network
    NETWORK_CHAINS = 'networkChains'
    
    # Page metrics
    PAGE_NOT_INTERACTABLE = 'pageNotInteractable'
    PAGE_SCROLLABLE = 'pageScrollable'

@dataclass
class NetworkState:
    """Enhanced structure for network state"""
    requests: List[Dict]  # Network requests with chain information
    analytics_tags: List[Dict]
    request_chains: List[Dict]  # Reconstructed request chains

@dataclass
class ConsentAction:
    """Structure for consent action results"""
    action_performed: bool
    action_successful: bool
    button_found: bool
    error: Optional[str]
    timestamp: float

@dataclass
class InteractionState:
    """Structure for interaction results"""
    consent: ConsentAction
    clickable_elements: List[Dict]
    interactions: List[Dict]
    network_state: NetworkState
    cookies: List[Dict]
    timestamp: float

@dataclass
class ConsentCheckResult:
    """Enhanced structure for consent check results"""
    url_info: Dict
    ccm_detection: Dict
    page_landing: Dict    # Initial state
    accept_flow: InteractionState
    reject_flow: InteractionState
    errors: List[str]

class DataCollectionService:

    def __init__(self, browser_manager: BrowserManager):
        self.browser = browser_manager
        self.errors: List[str] = []
        self.stored_element_info = []

    def _initialize_result(self, url_result: URLResult) -> ConsentCheckResult:

        """Initialize enhanced result structure"""
        return ConsentCheckResult(
            url_info={
                "requested_url": url_result.requested_url,
                "final_url": url_result.destination_url,
                "status_code": url_result.status_code,
                "domain": url_result.domain,
                "initial_accessibility": True
            },
            ccm_detection={
                "banner_found": False,
                "provider_name": "",
                "accessibility_with_banner": None,
                "can_scroll": None,
                "accessibility_issues": []
            },
            page_landing={
                "state": None,
                "timestamp": None
            },
            accept_flow=InteractionState(
                consent=ConsentAction(
                    action_performed=False,
                    action_successful=False,
                    button_found=False,
                    error=None,
                    timestamp=None
                ),
                clickable_elements=[],
                interactions=[],
                network_state=NetworkState(requests=[], analytics_tags=[], request_chains=[]),
                cookies=[],
                timestamp=None
            ),
            reject_flow=InteractionState(
                consent=ConsentAction(
                    action_performed=False,
                    action_successful=False,
                    button_found=False,
                    error=None,
                    timestamp=None
                ),
                clickable_elements=[],
                interactions=[],
                network_state=NetworkState(requests=[], analytics_tags=[], request_chains=[]),
                cookies=[],
                timestamp=None
            ),
            errors=[]
        )

    def create_result(self, url_result: URLResult) -> ConsentCheckResult:
        """Create structured result for a URL with pre and post consent states"""
        try:
            # Initialize empty result structure
            result = self._initialize_result(url_result)
            
            # A.1: Capture pre-consent state, detect banner, assess accessibility
            pre_consent_success = self._capture_pre_consent_state(url_result, result)
            if not pre_consent_success:
                return result

            provider = self.browser.current_provider
            # Only proceed with consent flows if we found a banner
            #TEMPORARY CHANGE FOR TESTING
            if provider:

                # A.2: Accept flow
                self._capture_post_consent_state(provider, result, 'accept')
                
                # Reset browser for reject flow
                self.browser.cleanup()
                self.browser = BrowserManager(self.browser.provider_registry)
                
                # A.3: Reject flow
                if self.browser.visit_url(url_result.destination_url):
                    self._capture_post_consent_state(provider, result, 'reject')
            result.errors = self.errors
            self.browser.cleanup()
            return result
            
        except Exception as e:
            self.errors.append(f"Error processing URL {url_result.destination_url}: {str(e)}")
            return result
    
    def _capture_pre_consent_state(self, url_result: URLResult, result: ConsentCheckResult) -> bool:

        """
        Capture complete pre-consent state including banner detection, accessibility,
        page state and clickable elements
        """
        try:
            # 1. Visit URL and wait for load
            if not self.browser.visit_url(url_result.destination_url):
                self.errors.append(f"Failed to visit URL: {url_result.destination_url}")
                return False

            
            
            # 2. Banner Detection
            provider = self.browser.detect_cookie_banner()
            self.browser.current_provider = provider  # Store for later use

            initial_state = self.browser.get_page_state(provider)
            
            # 4. Find meaningful clickable elements
            clickable_elements = self.browser.find_meaningful_clickables(
                limit=3,
                current_url=url_result.destination_url,
                banner_ids=provider.banner_ids if provider else None
            )
            # Store for later use in consent flows
            self.stored_elements = clickable_elements
            
            result.ccm_detection.update({
                "banner_found": provider is not None,
                "provider_name": provider.provider_name if provider else "",
            })

            if provider:
                # Perform accessibility checks
                accessibility_results = self.browser.check_site_accessibility(clickable_elements)
                
                result.ccm_detection.update({
                    "accessibility_with_banner": accessibility_results["is_accessible"],
                    "can_scroll": accessibility_results["can_scroll"],
                    "accessibility_issues": accessibility_results["issues"]
                })

                # Store accessibility issues if any
                if not accessibility_results["is_accessible"]:
                    self.errors.extend(accessibility_results["issues"])
            
            # 6. Update complete page landing state
            result.page_landing.update({
                "state": {
                    "cookies": initial_state.cookies,
                    "network_state": self._create_network_state(initial_state),
                    "analytics_tags": initial_state.analytics_tags,
                    "clickable_elements": [{
                        'text': elem['text'],
                        'href': elem['href'],
                        'opens_new_tab': elem['opens_new_tab']
                    } for elem in clickable_elements]
                },
                "timestamp": time.time()
            })

            # Success if we at least got the page state
            return bool(initial_state)

        except Exception as e:
            self.errors.append(f"Error in pre-consent capture: {str(e)}")
            return False
    
    def _capture_post_consent_state(self, provider: CookieProviderSignature, result: ConsentCheckResult, action: str) -> None:
        try:
            flow = result.accept_flow if action == 'accept' else result.reject_flow
            
            # Click consent button and capture result
            consent_status = self.browser.click_consent_button(provider, action=action)
            flow.consent = ConsentAction(
                action_performed=True,
                action_successful=consent_status['success'],
                button_found=consent_status['button_found'],
                error=consent_status['error'],
                timestamp=time.time()
            )

            # Restore stored elements for this session
            if consent_status['success'] and self.stored_elements:
                # Prepare elements for current session
                self.browser.restore_elements(self.stored_elements)
                # Use BrowserManager's interaction sequence
                flow.interactions = self.browser.perform_interaction_sequence()

            # Capture final state
            final_state = self.browser.get_page_state(provider=provider)
            flow.network_state = self._create_network_state(final_state)
            flow.cookies = final_state.cookies
            flow.timestamp = time.time()

        except Exception as e:
            self.errors.append(f"Error in {action} flow: {str(e)}")

    def _create_network_state(self, browser_state: BrowserState) -> NetworkState:
        """Create network state from browser state"""
        # Convert NetworkRequest objects to dictionaries
        requests = [{
            'url': req.url,
            'initiator': req.initiator,
            'timestamp': req.timestamp,
            'request_id': req.request_id,
            'is_third_party': req.is_third_party,
            'is_first_party': req.is_first_party,
            'is_ccm_provider': req.is_ccm_provider,
            'domain': req.domain
        } for req in browser_state.network_requests]

        # Reconstruct request chains
        chains = []
        for req in browser_state.network_requests:
            if req.initiator.get('type') == 'script':
                chain = {
                    'source': req.initiator.get('stack', {}).get('callFrames', [{}])[0].get('url', 'unknown'),
                    'target': req.url,
                    'timestamp': req.timestamp,
                    'type': 'script'
                }
                chains.append(chain)

        return NetworkState(
            requests=requests,
            analytics_tags=browser_state.analytics_tags,
            request_chains=chains
        )

    
    def generate_cod_results(self, result: ConsentCheckResult, include_network_chains: bool = True) -> dict:
        """
        Generate structured analysis of cookie and request behavior across consent states.
        
        Args:
            result: Raw collection results including pre and post consent states
            include_network_chains: Whether to include detailed request chain analysis
            
        Returns:
            Dictionary containing analysis of cookie and request behavior
        """
        def _analyze_cookies_and_requests(state_cookies: list, state_network: NetworkState) -> dict:
            """Analyze cookies and requests for a given state"""
            # Cookie classification
            first_party_cookies = [c for c in state_cookies if c.get('is_first_party', False)]
            third_party_cookies = [c for c in state_cookies if c.get('is_third_party', False)]
            ccm_provider_cookies = [c for c in state_cookies if c.get('is_ccm_provider', False)]
            
            # Request classification
            first_party_requests = [r for r in state_network.requests if r.get('is_first_party', False)]
            third_party_requests = [r for r in state_network.requests if r.get('is_third_party', False)]
            ccm_provider_requests = [r for r in state_network.requests if r.get('is_ccm_provider', False)]
            
            k = CookieAnalysisKeys
            analysis_dict = {
                k.FIRST_PARTY_COOKIES: len(first_party_cookies) > 0,
                k.CCM_PROVIDER_COOKIES: len(ccm_provider_cookies) > 0,
                k.NO_THIRD_PARTY_COOKIES: len(third_party_cookies) == 0,
                k.FIRST_PARTY_REQUESTS: len(first_party_requests) > 0,
                k.CCM_PROVIDER_REQUESTS: len(ccm_provider_requests) > 0,
                k.NO_THIRD_PARTY_REQUESTS: len(third_party_requests) == 0
            }
            
            if include_network_chains:
                analysis_dict[k.NETWORK_CHAINS] = state_network.request_chains
                
            return analysis_dict
        
        # Get states for different phases
        pre_consent_state = result.page_landing.get('state', {})
        pre_consent_analysis = _analyze_cookies_and_requests(
            pre_consent_state.get('cookies', []),
            pre_consent_state.get('network_state', NetworkState(requests=[], analytics_tags=[], request_chains=[]))
        )
        
        accept_analysis = _analyze_cookies_and_requests(
            result.accept_flow.cookies,
            result.accept_flow.network_state
        )
        
        reject_analysis = _analyze_cookies_and_requests(
            result.reject_flow.cookies,
            result.reject_flow.network_state
        )
        
        k = CookieAnalysisKeys
        # Build final analysis object
        analysis = {
            "url_info": {
                "requested_url": result.url_info['requested_url'],
                "final_url": result.url_info['final_url'],
                "status_code": result.url_info['status_code'],
                "domain": result.url_info['domain']
            },
            "ccm_banner": {
                "banner_found": result.ccm_detection['banner_found'],
                "provider_name": result.ccm_detection['provider_name']
            },
            "preConsent": {
                k.PAGE_NOT_INTERACTABLE: not result.ccm_detection['accessibility_with_banner'],
                k.PAGE_SCROLLABLE: result.ccm_detection["can_scroll"],
                k.FIRST_PARTY_COOKIES: pre_consent_analysis[k.FIRST_PARTY_COOKIES],
                k.CCM_PROVIDER_COOKIES: pre_consent_analysis[k.CCM_PROVIDER_COOKIES],
                k.NO_THIRD_PARTY_COOKIES: pre_consent_analysis[k.NO_THIRD_PARTY_COOKIES],
                k.FIRST_PARTY_REQUESTS: pre_consent_analysis[k.FIRST_PARTY_REQUESTS],
                k.CCM_PROVIDER_REQUESTS: pre_consent_analysis[k.CCM_PROVIDER_REQUESTS],
                k.NO_THIRD_PARTY_REQUESTS: pre_consent_analysis[k.NO_THIRD_PARTY_REQUESTS]
            },
            "postConsent": {
                "onAccept": {
                    k.FIRST_PARTY_COOKIES: accept_analysis[k.FIRST_PARTY_COOKIES],
                    k.CCM_PROVIDER_COOKIES: accept_analysis[k.CCM_PROVIDER_COOKIES],
                    k.NO_THIRD_PARTY_COOKIES: accept_analysis[k.NO_THIRD_PARTY_COOKIES],
                    k.FIRST_PARTY_REQUESTS: accept_analysis[k.FIRST_PARTY_REQUESTS],
                    k.CCM_PROVIDER_REQUESTS: accept_analysis[k.CCM_PROVIDER_REQUESTS],
                    k.NO_THIRD_PARTY_REQUESTS: accept_analysis[k.NO_THIRD_PARTY_REQUESTS]
                },
                "onReject": {
                    k.FIRST_PARTY_COOKIES: reject_analysis[k.FIRST_PARTY_COOKIES],
                    k.CCM_PROVIDER_COOKIES: reject_analysis[k.CCM_PROVIDER_COOKIES],
                    k.NO_THIRD_PARTY_COOKIES: reject_analysis[k.NO_THIRD_PARTY_COOKIES],
                    k.FIRST_PARTY_REQUESTS: reject_analysis[k.FIRST_PARTY_REQUESTS],
                    k.CCM_PROVIDER_REQUESTS: reject_analysis[k.CCM_PROVIDER_REQUESTS],
                    k.NO_THIRD_PARTY_REQUESTS: reject_analysis[k.NO_THIRD_PARTY_REQUESTS]
                }
            }
        }
        
        # Add network chains data if requested
        if include_network_chains:
            analysis["preConsent"][k.NETWORK_CHAINS] = pre_consent_analysis[k.NETWORK_CHAINS]
            analysis["postConsent"]["onAccept"][k.NETWORK_CHAINS] = accept_analysis[k.NETWORK_CHAINS]
            analysis["postConsent"]["onReject"][k.NETWORK_CHAINS] = reject_analysis[k.NETWORK_CHAINS]
        
        return analysis


    def _create_error_result(self, url_result: URLResult) -> ConsentCheckResult:
        """Create error result structure"""
        result = self._initialize_result(url_result)
        result.errors = self.errors
        return result
    
    