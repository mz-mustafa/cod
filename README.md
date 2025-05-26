# Cookie Consent Management (CCM) Analysis Tool
**A proof-of-concept tool for automated analysis of cookie consent compliance and website accessibility.**
## About
This prototype tool provides comprehensive analysis of website cookie consent implementations, helping organizations assess their compliance with privacy regulations like GDPR. The tool automatically detects cookie banners, tests website accessibility, and monitors network behavior across different consent states to identify potential compliance issues.
## Features
### 🔍 Cookie Banner Detection

- Automatically detects major CCM providers (OneTrust, TrustArc, Usercentrics/Cookiebot)
- Identifies banner elements and consent buttons
- Supports extensible provider registry for new CCM platforms

### 🌐 Multi-State Analysis

- Pre-consent: Analyzes initial page state before user interaction
- Post-consent (Accept): Monitors behavior after accepting cookies
- Post-consent (Reject): Monitors behavior after rejecting cookies

### 🍪 Cookie & Network Monitoring

- Tracks first-party, third-party, and CCM provider cookies
- Monitors network requests and request chains
- Detects analytics container loads (Google Analytics, Adobe Analytics)
- Classifies cookie security attributes (Secure, HttpOnly, SameSite)

### ♿ Accessibility Testing

- Tests whether websites remain accessible before consent is given
- Checks if users can scroll and interact with content pre-consent
- Identifies potential "cookie walls" that block site functionality

### 📊 Interactive Visualizations

- D3.js-powered network request chain visualizations
- Color-coded nodes showing different request types
- Interactive diagrams with zoom and pan capabilities
- Visual representation of cookie-setting relationships

### 📋 Comprehensive Reporting

- Structured JSON output with detailed compliance metrics
- Cookie summaries with security analysis
- Flag-based compliance indicators with interpretations
- Detailed error reporting and issue identification

## Architecture
├── browser_manager.py      # Selenium-based browser automation

├── data_collection.py      # Main data collection orchestration

├── provider_registry.py    # CCM provider signatures and detection

├── d3_visualisation.py     # Network visualization generation

├── url_processor.py        # URL validation and processing

└── main.ipynb             # Jupyter notebook interface

## Quick Start
### Prerequisites
- Python 3.8+
- Chrome/Chromium browser
- ChromeDriver
- Jupyter Notebook

### Installation
```
bash# Clone the repository
git clone https://github.com/yourusername/ccm-analysis-tool.git
cd ccm-analysis-tool
```

**Install dependencies**
pip install selenium requests jupyter pandas tld
Install ChromeDriver (or ensure it's in PATH)
Download from: https://chromedriver.chromium.org/

## Usage
Run the main analysis:
```
bash jupyter notebook main.ipynb
```
The notebook will:

- Process your target URLs
- Generate compliance analysis reports
- Create interactive network visualizations
- Export results as JSON files

### Key outputs:

- Compliance analysis JSON files
- Interactive HTML visualizations
- Cookie behavior summaries
- Accessibility test results

Example Analysis Output
```
 json{
  "ccm_banner": {
    "banner_found": true,
    "provider_name": "OneTrust"
  },
  "preConsent": {
    "pageNotInteractable": {
      "value": false,
      "outlook": "Negative",
      "meaning": "Users can interact with page before consent"
    },
    "noThirdPartyCookies": {
      "value": true,
      "outlook": "Positive", 
      "meaning": "No third party cookies detected"
    }
  }
}
```

## Key Compliance Metrics
### Pre-Consent Analysis

- No Third-Party Cookies: Ensures no tracking before consent
- Page Accessibility: Verifies users can access content
- Network Request Classification: Identifies request types and origins

### Post-Consent Analysis

- Consent Respect: Verifies different behavior for accept vs reject
- Cookie Classification: Analyzes security attributes
- Analytics Activation: Monitors when tracking starts

## Limitations (Proof of Concept)

- Browser Support: Currently Chrome/Chromium only
- CCM Coverage: Limited to major providers (extensible architecture)
- Scale: Designed for individual site analysis, not bulk processing
- Dynamic Content: May miss JavaScript-heavy consent implementations
- Legal Interpretation: Provides technical analysis, not legal advice

## Repository Scope
This public repository contains the core data collection and analysis components. An additional AI-powered risk assessment component that processes the JSON outputs is not included in this public release due to company policy restrictions.

## Use Cases

- Privacy Compliance Auditing: Automated GDPR/CCPA compliance checking
- Development Testing: Validate consent implementation during development
- Competitive Analysis: Understand how other sites handle consent
- Research: Academic study of web privacy implementations

## Future Enhancements - Confidential

## Technical Notes

Headless Browser: Uses Chrome in headless mode for automated testing
Network Monitoring: Captures network logs via Chrome DevTools Protocol
State Management: Maintains browser state across consent interactions
Visualization: Generates standalone HTML files with embedded D3.js

## Disclaimer
This tool provides technical analysis of website behavior and is not a substitute for legal advice. Cookie consent compliance requirements vary by jurisdiction and should be validated with legal counsel.

## License
Copyright (c) 2025 [Cressive Digital]. All rights reserved.
This code is made available for viewing and educational purposes only. Any use, copying, modification, or distribution requires explicit written permission from the author.
For usage permissions, please contact: [mustafa@cressive.com]

**Note: This is a prototype/proof-of-concept tool developed for research and testing purposes.**
