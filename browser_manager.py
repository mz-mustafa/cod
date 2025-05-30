import re
from typing import Any, Dict, List, Optional, Tuple
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
from urllib.parse import urlparse
from tld import get_fld

class NetworkRequest:
    """Enhanced structure for network request data"""
    def __init__(self, url: str, initiator: Dict, timestamp: float, request_id: str):
        self.url = url
        self.initiator = initiator
        self.timestamp = timestamp
        self.request_id = request_id
        self.domain = urlparse(url).netloc
        self.is_third_party = None
        self.is_first_party = None
        self.is_ccm_provider = None
        self.is_analytics_container = None
        self.analytics_provider = None
        self.sets_cookies = []

class BrowserState:
    """Enhanced browser state information"""
    def __init__(self):
        self.cookies: List[Dict] = []
        self.analytics_tags: List[Dict] = []
        self.network_requests: List[NetworkRequest] = []
        self.page_domain: str = ""

    def classify_parties(self, page_domain: str, provider: CookieProviderSignature):
        """
        Classify cookies and requests with all flags:
        is_ccm_provider, is_first_party, is_third_party, is_analytics_container
        
        Args:
            page_domain: Domain of the current page
            provider: Current CCM provider signature
        """
        self.page_domain = page_domain
        base_domain = get_fld(page_domain, fix_protocol=True)
        provider_base_domain = provider.provider_base_domain if provider else None
        
        # Classify cookies
        for cookie in self.cookies:
            cookie_domain = cookie.get('domain', '').lstrip('.')
            try:
                cookie_base_domain = get_fld(cookie_domain, fix_protocol=True)
                
                # First check if it's a CCM provider domain
                if provider_base_domain and cookie_base_domain == provider_base_domain:
                    cookie['is_ccm_provider'] = True
                    cookie['is_first_party'] = False
                    cookie['is_third_party'] = False
                # Then check if it's first party
                elif cookie_base_domain == base_domain:
                    cookie['is_ccm_provider'] = False
                    cookie['is_first_party'] = True
                    cookie['is_third_party'] = False
                # Otherwise it's third party
                else:
                    cookie['is_ccm_provider'] = False
                    cookie['is_first_party'] = False
                    cookie['is_third_party'] = True
            except Exception:
                # If domain parsing fails, consider it third party
                cookie['is_ccm_provider'] = False
                cookie['is_first_party'] = False
                cookie['is_third_party'] = True
            
        # Get a reference to the provider registry to check analytics providers
        provider_registry = getattr(provider, '_registry', None)
        
        # Classify network requests
        for request in self.network_requests:
            try:
                request_base_domain = get_fld(request.domain, fix_protocol=True)
                
                # First check if it's a CCM provider domain
                if provider_base_domain and request_base_domain == provider_base_domain:
                    request.is_ccm_provider = True
                    request.is_first_party = False
                    request.is_third_party = False
                    request.is_analytics_container = False
                # Then check if it's first party
                elif request_base_domain == base_domain:
                    request.is_ccm_provider = False
                    request.is_first_party = True
                    request.is_third_party = False
                    request.is_analytics_container = False
                # Otherwise it's third party, but might be an analytics container
                else:
                    request.is_ccm_provider = False
                    request.is_first_party = False
                    
                    # Check if this is an analytics container request
                    if provider_registry:
                        # Use the improved detection methods
                        container_results = provider_registry.is_analytics_container_load(request.url, request.domain)
                        is_container = any(container_results.values())
                        
                        if is_container:
                            # Find which provider matched
                            for provider_key, matched in container_results.items():
                                if matched:
                                    provider = provider_registry._analytics_providers.get(provider_key)
                                    if provider:
                                        request.analytics_provider = provider.provider_name
                                        break
                        
                        request.is_analytics_container = is_container
                        
                        # If it's an analytics container, it's not considered a regular third-party request
                        if is_container:
                            request.is_third_party = False
                        else:
                            request.is_third_party = True
                    else:
                        request.is_analytics_container = False
                        request.is_third_party = True
                        
            except Exception:
                # If domain parsing fails, consider it third party
                request.is_ccm_provider = False
                request.is_first_party = False
                request.is_third_party = True
                request.is_analytics_container = False

        # Add classification for cookies set by network requests
        for request in self.network_requests:
            for cookie in request.sets_cookies:
                cookie_domain = cookie.get('domain', '').lstrip('.')
                try:
                    cookie_base_domain = get_fld(cookie_domain, fix_protocol=True)
                    
                    # First check if it's a CCM provider domain
                    if provider_base_domain and cookie_base_domain == provider_base_domain:
                        cookie['type'] = 'ccm_provider'
                    # Then check if it's first party
                    elif cookie_base_domain == base_domain:
                        cookie['type'] = 'first_party'
                    # Otherwise it's third party
                    else:
                        cookie['type'] = 'third_party'
                except Exception:
                    # If domain parsing fails, consider it third party
                    cookie['type'] = 'third_party'
    
    
    def _get_base_domain(self, domain: str) -> str:
        """Extract base domain from domain string"""
        parts = domain.split('.')
        return '.'.join(parts[-2:]) if len(parts) > 2 else domain

    def _is_same_domain(self, domain1: str, domain2: str) -> bool:
        """Compare two domains, handling subdomains"""
        return self._get_base_domain(domain1) == self._get_base_domain(domain2)
    

class BrowserManager:
    def __init__(self, provider_registry: ProviderRegistry):
        self.provider_registry = provider_registry
        self.driver = None
        self.current_page_domain = None
        self.network_logs = []
        self.setup_browser()
        
    def setup_browser(self):
        """Initialize Chrome with enhanced logging"""
        options = Options()
        options.headless = True
        options.add_argument('--enable-logging')
        options.set_capability('goog:loggingPrefs', {'performance': 'ALL'})
        options.add_experimental_option('perfLoggingPrefs', {
            'enableNetwork': True,
            #'enablePage': True,
            #'traceCategories': 'browser,devtools.timeline,devtools'
        })
        
        self.driver = webdriver.Chrome(options=options)
        # Enable detailed network monitoring
        self.driver.execute_cdp_cmd('Network.enable', {})
        self.request_cookie_map = {}
        
    def visit_url(self, url: str) -> bool:
        """Visit URL and set current domain"""
        try:
            self.driver.get(url)
            self.current_page_domain = urlparse(url).netloc
            WebDriverWait(self.driver, 10).until(
                lambda driver: driver.execute_script('return document.readyState') == 'complete'
            )
            # Clear previous network logs
            self.network_logs = []
            return True
        except Exception as e:
            print(f"Error visiting URL {url}: {str(e)}")
            return False
            
    def get_page_state(self, provider) -> BrowserState:
        """Capture enhanced page state with JavaScript cookie detection"""
        state = BrowserState()
        
        try:
            # Capture initial cookies before page interactions
            initial_cookie_cmd = self.driver.execute_cdp_cmd('Network.getAllCookies', {})
            initial_cookies = initial_cookie_cmd.get('cookies', [])
            initial_cookie_map = {f"{c.get('name')}@{c.get('domain')}": c for c in initial_cookies}
            
            print(f"Initial cookies count: {len(initial_cookies)}")
            
            # Wait for potential dynamic cookie setting
            time.sleep(2)
            
            # Get cookies after page load/wait
            final_cookie_cmd = self.driver.execute_cdp_cmd('Network.getAllCookies', {})
            final_cookies = final_cookie_cmd.get('cookies', [])
            
            print(f"Final cookies count: {len(final_cookies)}")
            
            # Normalize CDP cookie format to match Selenium format
            normalized_cookies = []
            for cookie in final_cookies:
                normalized_cookie = {
                    'name': cookie.get('name'),
                    'value': cookie.get('value'),
                    'domain': cookie.get('domain'),
                    'path': cookie.get('path'),
                    'expiry': cookie.get('expires'),
                    'secure': cookie.get('secure', False),
                    'httpOnly': cookie.get('httpOnly', False),
                    'sameSite': cookie.get('sameSite', 'None')
                }
                normalized_cookies.append(normalized_cookie)
                    
            state.cookies = normalized_cookies
            
            # Get analytics tags
            state.analytics_tags = self._check_analytics_tags()
            
            # Get network requests with the original method (not the debug version)
            state.network_requests = self._get_network_requests()
            
            # Identify new cookies (set via JavaScript)
            new_cookies = []
            for cookie in final_cookies:
                cookie_key = f"{cookie.get('name')}@{cookie.get('domain')}"
                if cookie_key not in initial_cookie_map:
                    new_cookies.append({
                        'name': cookie.get('name'),
                        'domain': cookie.get('domain'),
                        'type': None
                    })
                    print(f"New cookie detected: {cookie.get('name')} for domain {cookie.get('domain')}")
            
            # If there are no new cookies, but we still want to associate cookies with requests
            if not new_cookies:
                print("No new cookies detected, associating existing cookies with relevant requests...")
                for cookie in normalized_cookies:
                    cookie_domain = cookie.get('domain', '').lstrip('.')
                    for req in state.network_requests:
                        req_domain = req.domain
                        if (req_domain.endswith(cookie_domain) or cookie_domain.endswith(req_domain)):
                            # Avoid duplicate entries
                            cookie_entry = {
                                'name': cookie.get('name'),
                                'domain': cookie_domain,
                                'type': None
                            }
                            if not any(c.get('name') == cookie.get('name') for c in req.sets_cookies):
                                req.sets_cookies.append(cookie_entry)
            
            # Classify everything
            if self.current_page_domain:
                state.classify_parties(self.current_page_domain, provider)
                
        except Exception as e:
            print(f"Error capturing page state: {str(e)}")
                
        return state
    
    
    def _get_network_requests(self) -> List[NetworkRequest]:
        """Enhanced network request capture with chain information"""
        network_requests = []
        
        # Get new logs since last check
        logs = self.driver.get_log('performance')
        self.network_logs.extend(logs)
        
        # Process all logs to build request chains
        for entry in self.network_logs:
            try:
                network_log = json.loads(entry['message'])['message']
                
                if network_log['method'] == 'Network.requestWillBeSent':
                    params = network_log['params']
                    
                    # Create network request object
                    request = NetworkRequest(
                        url=params['request']['url'],
                        initiator=params['initiator'],
                        timestamp=params['timestamp'],
                        request_id=params['requestId']
                    )
                    
                    network_requests.append(request)
                    # Store for cookie correlation
                    self.request_cookie_map[params['requestId']] = request
                    
            except Exception as e:
                print(f"Error processing network log: {str(e)}")
        
        # Second pass: Find Set-Cookie headers in responses
        for entry in self.network_logs:
            try:
                network_log = json.loads(entry['message'])['message']
                
                if network_log['method'] == 'Network.responseReceived':
                    params = network_log['params']
                    request_id = params['requestId']
                    
                    # If we have this request in our map
                    if request_id in self.request_cookie_map:
                        request = self.request_cookie_map[request_id]
                        
                        # Look for Set-Cookie headers
                        if 'response' in params and 'headers' in params['response']:
                            headers = params['response']['headers']
                            cookies_set = []
                            
                            # Handle uppercase and lowercase header names
                            for header_name in ['Set-Cookie', 'set-cookie']:
                                if header_name in headers:
                                    cookie_headers = headers[header_name]
                                    # Convert to list if single string
                                    if isinstance(cookie_headers, str):
                                        cookie_headers = [cookie_headers]
                                        
                                    for cookie_header in cookie_headers:
                                        try:
                                            # Parse the cookie
                                            cookie_parts = cookie_header.split(';')[0].split('=', 1)
                                            cookie_name = cookie_parts[0].strip()
                                            cookie_domain = self._extract_domain_from_cookie(cookie_header, request.domain)
                                            
                                            cookies_set.append({
                                                'name': cookie_name,
                                                'domain': cookie_domain,
                                                # We'll set type later in classify_parties
                                                'type': None
                                            })
                                        except Exception as e:
                                            print(f"Error parsing cookie: {str(e)}")
                                            
                            # Store cookies with this request
                            request.sets_cookies = cookies_set
            
            except Exception as e:
                print(f"Error processing response log: {str(e)}")
                
        return network_requests

    def detect_cookie_banner(self) -> Optional[CookieProviderSignature]:
        """
        Only detects banner and returns provider if found.
        No accessibility checks included.
        """
        try:
            # Wait for page to be fully loaded
            WebDriverWait(self.driver, 10).until(
                lambda driver: driver.execute_script('return document.readyState') == 'complete'
            )
            # Give extra time for banner to appear
            time.sleep(2)
            
            page_source = self.driver.page_source
            provider = self.provider_registry.get_provider(page_source)
            
            if provider:
                # Attach provider registry to the provider instance for analytics detection
                provider._registry = self.provider_registry
                
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
    
    def _extract_domain_from_cookie(self, cookie_header: str, default_domain: str) -> str:
        """Extract domain from cookie header or use default"""
        domain_match = re.search(r'domain=([^;]+)', cookie_header, re.IGNORECASE)
        if domain_match:
            return domain_match.group(1).strip()
        return default_domain
    
    def find_meaningful_clickables(self, limit: int, current_url: str, banner_ids: Optional[List[str]] = None) -> List[Dict]:
        """
        Find meaningful clickable elements excluding banner and navigation elements.
        
        Args:
            limit: Maximum number of elements to return
            current_url: Current page URL to exclude self-references
            banner_ids: List of banner element IDs to exclude
        
        Returns:
            List of dictionaries containing element information
        """
        clickable_elements = []
        
        try:
            # Get banner elements to exclude if banner_ids provided
            banner_elements = set()
            if banner_ids:
                for banner_id in banner_ids:
                    try:
                        banner = self.driver.find_element(By.ID, banner_id)
                        banner_elements.add(banner)
                    except NoSuchElementException:
                        continue

            # Find all anchor elements
            elements = self.driver.find_elements(By.TAG_NAME, "a")
            for element in elements:
                if len(clickable_elements) >= limit:
                    break
                    
                try:
                    if element.is_displayed() and element.is_enabled():
                        # Skip if element is part of cookie banner
                        if banner_elements and any(self._is_child_of(element, banner) for banner in banner_elements):
                            continue
                            
                        href = element.get_attribute('href')
                        target = element.get_attribute('target')
                        
                        # Skip if:
                        # - No href
                        # - Same as current page
                        # - JavaScript void
                        # - Anchor link
                        if (not href or 
                            href == current_url or 
                            href.startswith('javascript:') or 
                            href.startswith('#')):
                            continue
                        else:
                            is_clickable = True
                        # Check if actually clickable
                        #is_clickable = self._execute_js("""
                        #    var elem = arguments[0];
                        #    var rect = elem.getBoundingClientRect();
                        #    var cx = rect.left + rect.width/2;
                        #    var cy = rect.top + rect.height/2;
                        #    var element = document.elementFromPoint(cx, cy);
                        #    return element === elem;
                        #""", element)
                        
                        if is_clickable:
                            element_info = {
                                'element': element,
                                'text': element.text.strip(),
                                'href': href,
                                'opens_new_tab': target == '_blank'
                            }
                            clickable_elements.append(element_info)
                            
                except Exception:
                    continue
                        
        except Exception as e:
            print(f"Error finding clickable elements: {str(e)}")
                
        return clickable_elements

    def check_site_accessibility(self, clickable_elements: List[Dict]) -> Dict[str, Any]:
        """
        Check site accessibility focusing on element clickability.
        
        Args:
            clickable_elements: List of clickable elements to test
        
        Returns:
            Dictionary containing accessibility test results
        """
        results = {
            "is_accessible": False,
            "can_scroll": False,
            "can_interact": False,
            "issues": [],
            "clickable_elements_status": []
        }
        
        try:
            # Scroll check - kept as UX metric
            original_height = self._execute_js("return window.pageYOffset;")
            self._execute_js("window.scrollTo(0, 100);")
            new_height = self._execute_js("return window.pageYOffset;")
            results["can_scroll"] = original_height != new_height
            
            if not results["can_scroll"]:
                results["issues"].append("Page scrolling is blocked (UX issue)")
            
            # Test clickability of provided elements
            clickable_count = 0
            
            for element_info in clickable_elements:
                element_status = {
                    "text": element_info["text"],
                    "href": element_info["href"],
                    "is_clickable": False,
                    "error": None
                }
                
                try:
                    element = element_info["element"]
                    
                    # Check if element is still in viewport and clickable
                    is_clickable = self._execute_js("""
                        var elem = arguments[0];
                        var rect = elem.getBoundingClientRect();
                        var cx = rect.left + rect.width/2;
                        var cy = rect.top + rect.height/2;
                        
                        // Check if element is in viewport
                        if (rect.top < 0 || rect.left < 0 || 
                            rect.bottom > window.innerHeight || 
                            rect.right > window.innerWidth) {
                            return false;
                        }
                        
                        var element = document.elementFromPoint(cx, cy);
                        return element === elem;
                    """, element)
                    
                    if is_clickable:
                        clickable_count += 1
                        element_status["is_clickable"] = True
                        element_status["error"] = "Element is clickable at pre-consent stage"
                        
                        
                except Exception as e:
                    element_status["error"] = str(e)
                    
                results["clickable_elements_status"].append(element_status)
                
            # Site is considered accessible if at least one meaningful element is clickable
            results["can_interact"] = clickable_count > 0
            results["is_accessible"] = results["can_interact"]
            
            if results["can_interact"]:
                results["issues"].append("Element is clickable at pre-consent stage")
                
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

    def _is_child_of(self, element: Any, parent: Any) -> bool:
        """Check if element is child of parent"""
        try:
            current = element
            while current:
                if current == parent:
                    return True
                current = current.find_element(By.XPATH, '..')
            return False
        except:
            return False
    
    def click_consent_button(self, provider: CookieProviderSignature, action: str = 'reject') -> Dict:
        """Enhanced consent button interaction with detailed status"""
        self.current_provider = provider
        result = {
            'action': action,
            'success': False,
            'error': None,
            'button_found': False
        }
        
        try:
            button_ids = provider.reject_button_ids if action == 'reject' else provider.accept_button_ids
            
            for button_id in button_ids:
                try:
                    element = self.driver.find_element(By.ID, button_id)
                    if element.is_displayed():
                        result['button_found'] = True
                        element.click()
                        result['success'] = True
                        return result
                except NoSuchElementException:
                    continue
                except Exception as e:
                    result['error'] = f"Error clicking button: {str(e)}"
                    return result
                    
            if not result['button_found']:
                result['error'] = f"No visible {action} button found"
                
        except Exception as e:
            result['error'] = f"Error in consent flow: {str(e)}"
            
        return result

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
        
    
    
    def perform_interaction_sequence(self) -> List[Dict]:
        """
        Perform click sequence on stored elements with enhanced error handling
        Returns detailed interaction results
        """
        if not hasattr(self, 'stored_elements'):
            raise Exception("No stored elements found. Run store_clickable_elements first")
            
        interaction_results = []
        
        for element_info in self.stored_elements:
            result = {
                'element_text': element_info['text'],
                'href': element_info['href'],
                'opens_new_tab': element_info['opens_new_tab'],
                'before_click_url': self.driver.current_url,
                'success': False,
                'landed_on_url': None,
                'interaction_type': 'new_tab' if element_info['opens_new_tab'] else 'same_window',
                'error': None
            }
            
            try:
                if element_info['opens_new_tab']:
                    # Handle new tab scenario
                    original_window = self.driver.current_window_handle
                    
                    # Click and wait for new window
                    element_info['element'].click()
                    wait = WebDriverWait(self.driver, 3)
                    wait.until(EC.number_of_windows_to_be(2))
                    
                    # Switch to new window
                    new_window = [window for window in self.driver.window_handles if window != original_window][0]
                    self.driver.switch_to.window(new_window)
                    
                    # Record success
                    result['success'] = True
                    result['landed_on_url'] = self.driver.current_url
                    
                    # Close new window and switch back
                    self.driver.close()
                    self.driver.switch_to.window(original_window)
                else:
                    # Regular click in same window
                    if self.click_element_and_wait(element_info):
                        result['success'] = True
                        result['landed_on_url'] = self.driver.current_url
                        self.navigate_back()
                    else:
                        result['error'] = "Click failed or page load timeout"
                        
            except Exception as e:
                result['error'] = str(e)
                # Try to recover to original window if needed
                if element_info['opens_new_tab']:
                    try:
                        self.driver.switch_to.window(original_window)
                    except:
                        pass
                
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
         
    def restore_elements(self, element_info_list: List[Dict]) -> None:
        """Restore previously stored elements for current session"""
        self.stored_elements = []
        for info in element_info_list:
            try:
                element = self.driver.find_element(
                    By.XPATH, 
                    f"//a[contains(@href,'{info['href']}')]"
                )
                if element.is_displayed() and element.is_enabled():
                    self.stored_elements.append({
                        'element': element,
                        'text': info['text'],
                        'href': info['href'],
                        'opens_new_tab': info['opens_new_tab']
                    })
            except Exception:
                continue

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