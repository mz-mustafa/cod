import pytest
from unittest.mock import Mock, patch
import requests
from requests.exceptions import Timeout, ConnectionError, TooManyRedirects
from url_processor import URLProcessor, URLResult, AnalyticsType

@pytest.fixture
def url_processor():
    return URLProcessor(timeout=5)

@pytest.fixture
def mock_responses():
    # Standard 200 response
    success = Mock()
    success.url = "https://example.com"
    success.status_code = 200
    
    # Redirect response
    redirect = Mock()
    redirect.url = "https://example.com/new"
    redirect.status_code = 301
    
    # Server error
    server_error = Mock()
    server_error.url = "https://error.com"
    server_error.status_code = 500
    
    # Rate limit response
    rate_limit = Mock()
    rate_limit.url = "https://ratelimit.com"
    rate_limit.status_code = 429
    
    return {
        'success': success,
        'redirect': redirect,
        'server_error': server_error,
        'rate_limit': rate_limit
    }

def test_validate_url(url_processor):
    """Test URL validation with various formats"""
    valid_urls = [
        "https://example.com",
        "http://example.com",
        "https://sub.example.com",
        "https://example.com/path?param=value",
        "http://example.com:8080"
    ]
    
    invalid_urls = [
        "",
        "not-a-url",
        "http://",
        "https://",
        "ftp://example.com",  # We might want to support this later
        "example.com",        # Missing scheme
        "https:/example.com"  # Missing slash
    ]
    
    for url in valid_urls:
        assert url_processor.validate_url(url) is True, f"Should be valid: {url}"
        
    for url in invalid_urls:
        assert url_processor.validate_url(url) is False, f"Should be invalid: {url}"

def test_domain_handling(url_processor):
    """Test domain extraction and comparison"""
    # Test domain extraction
    assert url_processor.check_domain("https://example.com") == "example.com"
    assert url_processor.check_domain("https://sub.EXAMPLE.com") == "sub.example.com"
    assert url_processor.check_domain("https://example.com/path") == "example.com"
    
    # Test domain comparison
    assert url_processor.is_same_domain(
        "https://example.com", 
        "http://example.com"
    ) is True
    
    assert url_processor.is_same_domain(
        "https://example.com", 
        "https://sub.example.com"
    ) is False
    
    # Edge cases
    with pytest.raises(Exception):
        url_processor.check_domain("not-a-url")

def test_analytics_mapping(url_processor):
    """Test analytics source mapping"""
    # Test known types
    assert url_processor.map_analytics_source("gtm") == "gtm"
    assert url_processor.map_analytics_source("GTM") == "gtm"
    assert url_processor.map_analytics_source("adobe") == "adobe"
    
    # Test unknown types
    assert url_processor.map_analytics_source("unknown") == "unknown"
    assert url_processor.map_analytics_source("") == "unknown"
    assert url_processor.map_analytics_source("invalid") == "unknown"

@patch('requests.Session')
def test_url_status_handling(mock_session, url_processor, mock_responses):
    """Test URL status handling for different scenarios"""
    success_response = Mock()
    success_response.url = "https://example.com"
    success_response.status_code = 200

    redirect_response = Mock()
    redirect_response.url = "https://example.com/new"
    redirect_response.status_code = 301

    def get_mock_response(url, **kwargs):
        if "example.com" in url:
            return success_response
        elif "redirect" in url:
            return redirect_response
        elif "error" in url:
            return mock_responses['server_error']
        elif "timeout" in url:
            raise Timeout("Request timed out")
        elif "connection" in url:
            raise ConnectionError("Failed to connect")
        elif "ratelimit" in url:
            return mock_responses['rate_limit']
        raise Exception("Unknown test URL")
    
    mock_session.return_value.get.side_effect = get_mock_response
    
    # Test successful request
    url, status = url_processor.get_url_status("https://example.com")
    assert status == 200
    assert url == "https://example.com"
    
    # Test redirect
    url, status = url_processor.get_url_status("https://redirect.com")
    assert status == 301  # Changed from 200 to 301
    assert url == "https://example.com/new"  # Updated expected URL

@patch('requests.Session')
def test_process_urls_comprehensive(mock_session, url_processor, mock_responses):
    """Test the complete URL processing workflow"""
    success_response = Mock()
    success_response.url = "https://example.com"
    success_response.status_code = 200

    redirect_response = Mock()
    redirect_response.url = "https://example.com/new"
    redirect_response.status_code = 301

    def get_mock_response(url, **kwargs):
        if "example.com" in url:
            return success_response
        elif "redirect" in url:
            return redirect_response
        elif "error" in url:
            return mock_responses['server_error']
        elif "timeout" in url:
            raise Timeout("Request timed out")
        return success_response
    
    mock_session.return_value.get.side_effect = get_mock_response
    
    test_urls = [
        "https://example.com",          # Success
        "not-a-url",                    # Invalid format
        "https://redirect.com",         # Redirect
        "https://error.com",           # Server error
        "https://timeout.com",         # Timeout
        "",                            # Empty string
        "https://example.com/path",    # Valid with path
        "https://",                    # Incomplete URL
    ]
    
    results = url_processor.process_urls(test_urls)
    
    # Check we got a result for each URL
    assert len(results) == len(test_urls)
    
    # Check success case
    assert results[0].status_code == 200
    assert results[0].is_valid == True
    
    # Check invalid URL
    assert results[1].is_valid == False
    assert "Invalid URL format" in results[1].error_message
    
    # Check redirect
    assert results[2].status_code == 301
    assert results[2].is_valid == True
    
    # Check server error
    assert results[3].status_code == 500
    assert results[3].is_valid == False
    
    # Check timeout
    assert results[4].is_valid == False
    assert "Request timed out" in results[4].error_message
    
    # Check empty string
    assert results[5].is_valid == False
    
    # Check valid URL with path
    assert results[6].is_valid == True
    assert results[6].status_code == 200
    
    # Check incomplete URL
    assert results[7].is_valid == False

if __name__ == "__main__":
    pytest.main([__file__])