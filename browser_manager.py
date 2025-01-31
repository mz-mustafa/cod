from typing import Dict, List, Optional, Tuple
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from provider_registry import ProviderRegistry, CookieProviderSignature
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium import webdriver
import json, time

class BrowserState:
    """Class to hold browser state information"""
    def __init__(self):
        self.cookies: List[Dict] = []
        self.analytics_tags: List[Dict] = []
        self.network_requests: List[str] = []

class BrowserManager:
    def __init__(self, provider_registry: ProviderRegistry):
        self.provider_registry = provider_registry
        self.driver = None
        self.setup_browser()
        
    def setup_browser(self):
        """Initialize Chrome in headless mode with CDP"""
        options = Options()
        options.headless = True
        options.add_argument('--enable-logging')  # Enable performance logging
        options.set_capability('goog:loggingPrefs', {'performance': 'ALL'})
        options.add_experimental_option('perfLoggingPrefs', {
            'enableNetwork': True,
            'enablePage': True,
        })
        
        self.driver = webdriver.Chrome(options=options)
        # Enable network monitoring
        self.driver.execute_cdp_cmd('Network.enable', {})
        
    def visit_url(self, url: str) -> bool:
        """Visit URL and return success status"""
        try:
            self.driver.get(url)
            WebDriverWait(self.driver, 10).until(
            lambda driver: driver.execute_script('return document.readyState') == 'complete'
            )   
            return True
        except Exception as e:
            print(f"Error visiting URL {url}: {str(e)}")
            return False
            
    def get_page_state(self) -> BrowserState:
        """Capture current page state including cookies and tags"""
        state = BrowserState()
        
        # Get cookies
        state.cookies = self.driver.get_cookies()
        
        # Check for analytics implementations
        state.analytics_tags = self._check_analytics_tags()
        
        # Get network requests
        state.network_requests = self._get_network_requests()
        
        return state
        
    def detect_cookie_banner(self) -> Tuple[Optional[CookieProviderSignature], Dict]:
        """
        Detect cookie banner and check accessibility
        Returns (provider, accessibility_results)
        """
        provider = self._detect_provider()
        if provider:
            accessibility = self.check_accessibility_with_banner()
            return provider, accessibility
        return None, None
    
    def _detect_provider(self) -> Optional[CookieProviderSignature]:
        """
        Internal method to detect cookie consent provider
        Returns provider signature if found, None otherwise
        """
        try:
            # Wait for page to be fully loaded
            WebDriverWait(self.driver, 10).until(
                lambda driver: driver.execute_script('return document.readyState') == 'complete'
            )
            # Give extra time for banner to appear
            time.sleep(2)  # Sometimes needed for dynamic content
            page_source = self.driver.page_source
            provider = self.provider_registry.get_provider(page_source)
            
            if provider:
                # Verify banner is actually present in DOM
                for banner_id in provider.banner_ids:
                    try:
                        element = self.driver.find_element(By.ID, banner_id)
                        if element.is_displayed():
                            return provider
                    except NoSuchElementException:
                        continue
            
            return None
        except Exception as e:
            print(f"Error detecting provider: {str(e)}")
            return None

    def check_accessibility_with_banner(self) -> Dict[str, any]:
        """
        Check if site is still accessible with cookie banner present.
        Site is considered accessible if interactive elements are clickable.
        Scroll check is maintained as a UX metric but doesn't affect accessibility status.
        """
        results = {
            "is_accessible": False,
            "can_scroll": False,
            "can_interact": False,
            "issues": []
        }
        
        try:
            # Scroll check - kept as UX metric
            original_height = self._execute_js("return window.pageYOffset;")
            self._execute_js("window.scrollTo(0, 100);")
            new_height = self._execute_js("return window.pageYOffset;")
            results["can_scroll"] = original_height != new_height
            
            if not results["can_scroll"]:
                results["issues"].append("Page scrolling is blocked (UX issue)")
            
            # Check interactive elements - this determines accessibility
            interactive_selectors = ["a", "button", "input", "select"]
            found_clickable = False
            for selector in interactive_selectors:
                try:
                    elements = self.driver.find_elements(By.TAG_NAME, selector)
                    for element in elements:
                        if element.is_displayed() and element.is_enabled():
                            # Check if element is not covered by banner
                            is_clickable = self._execute_js("""
                                var elem = arguments[0];
                                var rect = elem.getBoundingClientRect();
                                var cx = rect.left + rect.width/2;
                                var cy = rect.top + rect.height/2;
                                var element = document.elementFromPoint(cx, cy);
                                return element === elem;
                            """, element)
                            if is_clickable:
                                found_clickable = True
                                break
                    if found_clickable:
                        break
                except Exception as e:
                    continue
                    
            results["can_interact"] = found_clickable
            results["is_accessible"] = found_clickable  # Overall accessibility depends only on interaction
            
            if not results["can_interact"]:
                results["issues"].append("All interactive elements are blocked by banner")
                    
        except Exception as e:
            results["is_accessible"] = False
            results["issues"].append(f"Error checking accessibility: {str(e)}")
            
        return results

    def _execute_js(self, script: str, *args) -> any:
        """Execute JavaScript with arguments"""
        try:
            return self.driver.execute_script(script, *args)
        except Exception as e:
            print(f"Error executing JavaScript: {str(e)}")
            return None
        
    def click_consent_button(self, provider: CookieProviderSignature, action: str = 'reject') -> bool:
        """Click consent button (accept/reject) for given provider"""
        button_ids = provider.reject_button_ids if action == 'reject' else provider.accept_button_ids
        for button_id in button_ids:
            try:
                element = self.driver.find_element(By.ID, button_id)
                if element.is_displayed():
                    element.click()
                    return True
            except NoSuchElementException:
                continue
        return False

    def find_clickable_elements(self, limit: int = 3) -> List[Dict]:

        """Find first n clickable elements that navigate to different pages"""
        clickable_elements = []
        current_url = self.driver.current_url
        
        elements = self.driver.find_elements(By.TAG_NAME, "a")
        for element in elements:
            if len(clickable_elements) >= limit:
                break
                
            try:
                if element.is_displayed() and element.is_enabled():
                    href = element.get_attribute('href')
                    # Skip if no href or same as current page
                    if not href or href == current_url:
                        continue
                        
                    # Check if actually clickable
                    is_clickable = self._execute_js("""
                        var elem = arguments[0];
                        var rect = elem.getBoundingClientRect();
                        var cx = rect.left + rect.width/2;
                        var cy = rect.top + rect.height/2;
                        var element = document.elementFromPoint(cx, cy);
                        return element === elem;
                    """, element)
                    
                    if is_clickable:
                        element_info = {
                            'element': element,
                            'text': element.text,
                            'href': href
                        }
                        clickable_elements.append(element_info)
            except Exception:
                continue
                    
        return clickable_elements
    
    def click_element_and_wait(self, element_info: Dict) -> bool:
        """Click element and wait for any navigation"""
        try:
            element = element_info['element']
            element.click()
            
            # Wait for any navigation to complete
            WebDriverWait(self.driver, 10).until(
                lambda driver: driver.execute_script('return document.readyState') == 'complete'
            )
            return True
        except Exception as e:
            print(f"Error clicking element: {str(e)}")
            return False

    def navigate_back(self) -> bool:
        """Navigate back and wait for page load"""
        try:
            self.driver.back()
            WebDriverWait(self.driver, 10).until(
                lambda driver: driver.execute_script('return document.readyState') == 'complete'
            )
            return True
        except Exception as e:
            print(f"Error navigating back: {str(e)}")
            return False
        
    def store_clickable_elements(self) -> List[Dict]:
        """Find and store clickable elements for reuse"""
        self.stored_elements = self.find_clickable_elements(3)
        return self.stored_elements
    
    def perform_interaction_sequence(self) -> List[Dict]:
        """
        Perform click sequence on stored elements
        Returns interaction results
        """
        if not hasattr(self, 'stored_elements'):
            raise Exception("No stored elements found. Run store_clickable_elements first")
            
        interaction_results = []
        
        for element_info in self.stored_elements:
            result = {
                'element_text': element_info['text'],
                'href': element_info['href'],
                'before_click_url': self.driver.current_url,
                'success': False,
                'landed_on_url': None,
                'error': None
            }
            
            try:
                if self.click_element_and_wait(element_info):
                    result['success'] = True
                    result['landed_on_url'] = self.driver.current_url
                    self.navigate_back()
                else:
                    result['error'] = "Click failed"
            except Exception as e:
                result['error'] = str(e)
                
            interaction_results.append(result)
            
        return interaction_results

    def _check_analytics_tags(self) -> List[Dict]:
        """Check for presence of analytics implementations"""
        analytics_tags = []
        
        # Check Google Tag Manager
        gtm_script = self._execute_js("return typeof window.dataLayer !== 'undefined'")
        if gtm_script:
            analytics_tags.append({
                'type': 'gtm',
                'present': True
            })
            
        # Check Adobe Launch
        adobe_script = self._execute_js("return typeof window._satellite !== 'undefined'")
        if adobe_script:
            analytics_tags.append({
                'type': 'adobe',
                'present': True
            })
            
        return analytics_tags
        
    def _get_network_requests(self) -> List[str]:
        """Get network requests, focusing on analytics endpoints"""
        analytics_endpoints = [
            'google-analytics.com',
            'analytics.google.com',
            'doubleclick.net',
            'omtrdc.net',  # Adobe
            'demdex.net'   # Adobe
        ]
        
        # Get performance logs with Chrome
        logs = self.driver.get_log('performance')
        requests = []
        
        for entry in logs:
            try:
                # Parse log entry
                network_log = json.loads(entry['message'])['message']
                
                # Check if it's a network request
                if network_log['method'] == 'Network.requestWillBeSent':
                    url = network_log['params']['request']['url']
                    if any(endpoint in url for endpoint in analytics_endpoints):
                        requests.append(url)
            except Exception as e:
                print(f"Error processing network log: {str(e)}")
                    
        return requests
            
    def cleanup(self):
        """Clean up browser resources"""
        if self.driver:
            try:
                self.driver.quit()
            except Exception as e:
                print(f"Error during cleanup: {str(e)}")

    def __del__(self):
        """Ensure cleanup on object destruction"""
        self.cleanup()