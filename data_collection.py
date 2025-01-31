from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
from url_processor import URLResult
from browser_manager import BrowserManager, BrowserState
from provider_registry import CookieProviderSignature
import time
from selenium.webdriver.common.by import By


@dataclass
class ConsentCheckResult:
    """Complete structure for consent check results"""
    url_info: Dict
    ccm_detection: Dict
    page_landing: Dict    # Initial state
    accept_flow: Dict     # After accept + interactions
    reject_flow: Dict     # After reject + interactions
    errors: List[str]

class DataCollectionService:
    def __init__(self, browser_manager: BrowserManager):
        self.browser = browser_manager
        self.errors: List[str] = []
        self.stored_element_info = []

    def _initialize_result(self, url_result: URLResult) -> ConsentCheckResult:
        """Initialize result structure with URL info"""
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
                "accessibility_issues": []
            },
            page_landing={
                "state": None,
                "timestamp": None
            },
            accept_flow={
                "consent": {
                    "action_performed": False,
                    "action_successful": False
                },
                "clickable_elements": [],
                "interactions": [],
                "final_state": None,
                "timestamp": None
            },
            reject_flow={
                "consent": {
                    "action_performed": False,
                    "action_successful": False
                },
                "clickable_elements": [],
                "interactions": [],
                "final_state": None,
                "timestamp": None
            },
            errors=[]
        )
    

    def create_result(self, url_result: URLResult) -> ConsentCheckResult:
        """Create structured result for a URL"""
        try:
            # Initialize result structure
            result = self._initialize_result(url_result)
            
            # Process landing state and accept flow
            if self._process_landing_and_accept(url_result, result):
                # Restart browser for reject flow
                self.browser.cleanup()
                self.browser = BrowserManager(self.browser.provider_registry)
                
                # Process reject flow with fresh browser
                self._process_landing_and_reject(url_result, result)

            result.errors = self.errors
            return result

        except Exception as e:
            self.errors.append(f"Error processing URL {url_result.destination_url}: {str(e)}")
            return self._create_error_result(url_result)

    def _process_landing_and_accept(self, url_result: URLResult, result: ConsentCheckResult) -> bool:
        """Process landing state and accept flow"""
        try:
            if not self._process_landing_state(url_result, result):
                return False

            provider, accessibility_results = self.browser.detect_cookie_banner()
            if provider:
                self._process_banner_detection(provider, accessibility_results, result)
                
                # Find and store clickable elements
                clickable_elements = self.browser.store_clickable_elements()
                self.stored_element_info = [
                    {
                        'text': elem['text'],
                        'href': elem['href']
                    } for elem in clickable_elements
                ]
                
                self._process_accept_flow(provider, result)
                return True
            return False
        except Exception as e:
            self.errors.append(f"Error in accept flow: {str(e)}")
            return False

    def _process_landing_and_reject(self, url_result: URLResult, result: ConsentCheckResult) -> bool:
        """Process landing state and reject flow with fresh browser"""
        try:
            # Visit URL again
            if not self.browser.visit_url(url_result.destination_url):
                self.errors.append(f"Failed to visit URL for reject flow: {url_result.destination_url}")
                return False

            provider, _ = self.browser.detect_cookie_banner()
            if provider:
                # Find same elements as in accept flow
                stored_elements = []
                for info in self.stored_element_info:
                    try:
                        element = self.browser.driver.find_element(By.XPATH, 
                            f"//a[@href='{info['href']}'][text()='{info['text']}']")
                        if element.is_displayed() and element.is_enabled():
                            stored_elements.append({
                                'element': element,
                                'text': info['text'],
                                'href': info['href']
                            })
                    except Exception:
                        continue
                
                self.browser.stored_elements = stored_elements
                self._process_reject_flow(provider, result)
                return True
            return False
        except Exception as e:
            self.errors.append(f"Error in reject flow: {str(e)}")
            return False

    def _process_landing_state(self, url_result: URLResult, result: ConsentCheckResult) -> bool:
        """Process initial landing state"""
        if not self.browser.visit_url(url_result.destination_url):
            self.errors.append(f"Failed to visit URL: {url_result.destination_url}")
            return False

        # Get initial state
        initial_state = self.browser.get_page_state()
        result.page_landing["state"] = self._process_state(initial_state)
        result.page_landing["timestamp"] = time.time()
        return True

    def _process_banner_detection(self, provider: CookieProviderSignature, 
                                accessibility_results: Dict, 
                                result: ConsentCheckResult) -> None:
        """Process banner detection results"""
        result.ccm_detection["banner_found"] = True
        result.ccm_detection["provider_name"] = provider.provider_name
        result.ccm_detection["accessibility_with_banner"] = accessibility_results["is_accessible"]
        result.ccm_detection["accessibility_issues"] = accessibility_results.get("issues", [])

        if accessibility_results and not accessibility_results["is_accessible"]:
            self.errors.extend(accessibility_results["issues"])

    def _process_accept_flow(self, provider: CookieProviderSignature, result: ConsentCheckResult) -> None:

        """Process accept cookies flow and interactions"""
        try:
            print("Starting accept flow...")
            
            # Accept cookies
            accept_success = self.browser.click_consent_button(provider, action='accept')
            result.accept_flow["consent"]["action_performed"] = True
            result.accept_flow["consent"]["action_successful"] = accept_success
            print(f"Accept cookies action success: {accept_success}")

            # Store found clickable elements
            clickable_elements = self.browser.store_clickable_elements()
            result.accept_flow["clickable_elements"] = [
                {
                    'text': elem['text'],
                    'href': elem['href']
                } for elem in clickable_elements
            ]
            print(f"Found {len(clickable_elements)} clickable elements")

            # Perform interactions
            interaction_results = self.browser.perform_interaction_sequence()
            result.accept_flow["interactions"] = interaction_results
            print("Completed interaction sequence")

            # Get final state
            final_state = self.browser.get_page_state()
            result.accept_flow["final_state"] = self._process_state(final_state)
            result.accept_flow["timestamp"] = time.time()
            print("Accept flow completed")

        except Exception as e:
            error_msg = f"Error in accept flow: {str(e)}"
            self.errors.append(error_msg)
            print(error_msg)

    def _process_reject_flow(self, provider: CookieProviderSignature, result: ConsentCheckResult) -> None:

        """Process reject cookies flow and interactions"""
        try:
            print("Starting reject flow...")
            
            # Reject cookies
            reject_success = self.browser.click_consent_button(provider, action='reject')
            result.reject_flow["consent"]["action_performed"] = True
            result.reject_flow["consent"]["action_successful"] = reject_success
            print(f"Reject cookies action success: {reject_success}")

            # Use same clickable elements from accept flow for consistency
            if hasattr(self.browser, 'stored_elements'):
                result.reject_flow["clickable_elements"] = [
                    {
                        'text': elem['text'],
                        'href': elem['href']
                    } for elem in self.browser.stored_elements
                ]
                print("Using stored elements from accept flow")

                # Perform interactions
                interaction_results = self.browser.perform_interaction_sequence()
                result.reject_flow["interactions"] = interaction_results
                print("Completed interaction sequence")
            else:
                error_msg = "No stored elements found for reject flow"
                self.errors.append(error_msg)
                print(error_msg)

            # Get final state
            final_state = self.browser.get_page_state()
            result.reject_flow["final_state"] = self._process_state(final_state)
            result.reject_flow["timestamp"] = time.time()
            print("Reject flow completed")

        except Exception as e:
            error_msg = f"Error in reject flow: {str(e)}"
            self.errors.append(error_msg)
            print(error_msg)
    

    def create_summary(self, result: ConsentCheckResult) -> Dict:
        """Create a summarized version of the consent check result"""
        return {
            'url': result.url_info['requested_url'],
            'status': result.url_info['status_code'],
            'banner_found': result.ccm_detection['banner_found'],
            'provider': result.ccm_detection['provider_name'],
            'accessible': result.ccm_detection['accessibility_with_banner'],
            'accept_successful': result.accept_flow['consent']['action_successful'],
            'reject_successful': result.reject_flow['consent']['action_successful'],
            'initial_cookies': result.page_landing['state']['summary']['total_cookies'] if result.page_landing['state'] else 0,
            'accept_cookies': result.accept_flow['final_state']['summary']['total_cookies'] if result.accept_flow['final_state'] else 0,
            'reject_cookies': result.reject_flow['final_state']['summary']['total_cookies'] if result.reject_flow['final_state'] else 0,
            'has_errors': len(result.errors) > 0
        }
    
    def _process_state(self, state: BrowserState) -> Dict:
        """Process browser state into structured format"""
        return {
            "summary": {
                "total_cookies": len(state.cookies),
                "total_analytics_tags": len(state.analytics_tags),
                "total_analytics_requests": len(state.network_requests)
            },
            "details": {
                "cookies": state.cookies,
                "analytics_tags": state.analytics_tags,
                "network_requests": state.network_requests
            }
        }

    def _create_error_result(self, url_result: URLResult) -> ConsentCheckResult:
        """Create error result structure"""
        result = self._initialize_result(url_result)
        result.errors = self.errors
        return result