import requests
from bs4 import BeautifulSoup

def fetch_dom_text(url):
    """
    Fetch and extract text content from a URL's DOM.
    Uses advanced headers to bypass access denied errors.
    
    Args:
        url: The URL to fetch
    
    Returns:
        str: Extracted text from the page
    """
    from urllib.parse import urlparse
    parsed_url = urlparse(url)
    domain = f"{parsed_url.scheme}://{parsed_url.netloc}"
    homepage_url = f"{domain}/"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9,hi;q=0.8",
        "Accept-Encoding": "gzip, deflate, br, zstd",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Referer": homepage_url,
        "Cache-Control": "max-age=0",
        "DNT": "1"
    }
    
    # Create session to maintain cookies
    session = requests.Session()
    
    # First visit homepage to establish session
    try:
        session.get(homepage_url, headers=headers, timeout=15)
    except:
        pass  # Continue even if homepage fails
    
    # Now fetch the actual URL
    r = session.get(url, headers=headers, timeout=30)
    r.raise_for_status()
    
    # Check for access denied
    if "access denied" in r.text.lower() or "you don't have permission" in r.text.lower():
        raise Exception("Access denied error detected")
    
    soup = BeautifulSoup(r.text, "html.parser")
    return soup.get_text(separator="\n")

def fetch_dom_with_playwright(url):
    """
    Fetch DOM content using Playwright (handles JS-rendered content).
    Uses advanced techniques to bypass access denied errors.
    
    Args:
        url: The URL to fetch
    
    Returns:
        str: Extracted text from the page
    """
    from playwright.sync_api import sync_playwright
    from urllib.parse import urlparse
    
    parsed_url = urlparse(url)
    domain = f"{parsed_url.scheme}://{parsed_url.netloc}"
    homepage_url = f"{domain}/"
    
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=['--disable-blink-features=AutomationControlled', '--no-sandbox', '--disable-setuid-sandbox']
        )
        context = browser.new_context(
            viewport={"width": 1280, "height": 2000},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            locale="en-US",
            timezone_id="Asia/Kolkata"
        )
        page = context.new_page()
        
        # Remove webdriver property
        page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            window.chrome = { runtime: {} };
        """)
        
        headers = {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br, zstd",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Cache-Control": "max-age=0",
            "DNT": "1"
        }
        page.set_extra_http_headers(headers)
        
        # Visit homepage first to establish session
        try:
            page.goto(homepage_url, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(2000)
        except:
            pass
        
        # Update headers with referer for actual page
        headers["Referer"] = homepage_url
        headers["Sec-Fetch-Site"] = "same-origin"
        page.set_extra_http_headers(headers)
        
        # Navigate to target URL
        page.goto(url, wait_until="networkidle", timeout=30000)
        page.wait_for_timeout(2000)  # Wait for dynamic content
        
        # Check for access denied
        page_text = page.inner_text("body").lower()
        if "access denied" in page_text or "you don't have permission" in page_text:
            raise Exception("Access denied error detected")
        
        content = page.content()
        browser.close()
    
    soup = BeautifulSoup(content, "html.parser")
    return soup.get_text(separator="\n")

def extract_rating_from_dom(url):
    """
    Try to extract rating from DOM attributes/structure (for Flipkart/Amazon).
    Uses advanced techniques to bypass access denied errors.
    
    Args:
        url: The URL to fetch
    
    Returns:
        float or None: Rating value if found, None otherwise
    """
    from playwright.sync_api import sync_playwright
    from urllib.parse import urlparse
    import re
    
    try:
        parsed_url = urlparse(url)
        domain = f"{parsed_url.scheme}://{parsed_url.netloc}"
        homepage_url = f"{domain}/"
        
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=['--disable-blink-features=AutomationControlled', '--no-sandbox', '--disable-setuid-sandbox']
            )
            context = browser.new_context(
                viewport={"width": 1280, "height": 2000},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
                locale="en-US",
                timezone_id="Asia/Kolkata"
            )
            page = context.new_page()
            
            # Remove webdriver property
            page.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
                window.chrome = { runtime: {} };
            """)
            
            headers = {
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
                "Accept-Encoding": "gzip, deflate, br, zstd",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "none",
                "Sec-Fetch-User": "?1",
                "Cache-Control": "max-age=0",
                "DNT": "1"
            }
            page.set_extra_http_headers(headers)
            
            # Visit homepage first to establish session
            try:
                page.goto(homepage_url, wait_until="domcontentloaded", timeout=30000)
                page.wait_for_timeout(2000)
            except:
                pass
            
            # Update headers with referer
            headers["Referer"] = homepage_url
            headers["Sec-Fetch-Site"] = "same-origin"
            page.set_extra_http_headers(headers)
            
            page.goto(url, wait_until="networkidle", timeout=30000)
            page.wait_for_timeout(2000)
            
            # Check for access denied
            page_text = page.inner_text("body").lower()
            if "access denied" in page_text or "you don't have permission" in page_text:
                browser.close()
                return None
            
            # Try various selectors to find rating
            rating = None
            
            # Try Flipkart-specific patterns
            if "flipkart" in url.lower():
                selectors = [
                    '[class*="XQDdHH"]',  # Common Flipkart rating class
                    '[class*="Rating"]',
                    '[class*="rating"]',
                    '[itemprop="ratingValue"]',
                    '[aria-label*="rating"]',
                    '[aria-label*="Rating"]',
                ]
                for selector in selectors:
                    try:
                        elements = page.query_selector_all(selector)
                        for elem in elements[:5]:  # Check first 5 matches
                            text = elem.inner_text() or elem.get_attribute("aria-label") or ""
                            # Look for decimal number 0-5
                            match = re.search(r'(\d+\.?\d*)', text)
                            if match:
                                val = float(match.group(1))
                                if 0 <= val <= 5:
                                    rating = val
                                    break
                        if rating:
                            break
                    except:
                        continue
            
            # Try generic patterns for other sites
            if not rating:
                # Look in text content for rating patterns
                page_text = page.inner_text("body")
                patterns = [
                    r'(\d+\.?\d*)\s*(?:out\s+of\s+5|stars?|★|⭐)',
                    r'(\d+\.?\d*)\s*\/\s*5',
                ]
                for pattern in patterns:
                    match = re.search(pattern, page_text, re.IGNORECASE)
                    if match:
                        val = float(match.group(1))
                        if 0 <= val <= 5:
                            rating = val
                            break
            
            browser.close()
            return rating
    except Exception as e:
        print(f"Error extracting rating from DOM: {e}")
        return None

if __name__=="__main__":
    url = "https://www.meesho.com/example-product-url"
    try:
        txt = fetch_dom_text(url)
        print(txt[:2000])
    except Exception as e:
        print(f"DOM fetch failed: {e}, trying with Playwright...")
        txt = fetch_dom_with_playwright(url)
        print(txt[:2000])

