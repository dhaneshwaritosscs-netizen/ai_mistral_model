from playwright.sync_api import sync_playwright
from PIL import Image
import io

def capture_fullpage(url: str, out_path: str = "screenshot.png", viewport=(1280, 2000)):
    """
    Capture a full page screenshot of a URL using Playwright.
    Works on all URLs including Myntra, Amazon, Flipkart, Ajio, Meesho etc.
    Uses advanced anti-bot detection techniques to bypass access denied errors.
    
    Args:
        url: The URL to capture
        out_path: Output path for the screenshot
        viewport: Viewport size (width, height)
    
    Returns:
        str: Path to the saved screenshot
    """
    url_lower = url.lower()
    
    # For Myntra, try multiple strategies
    if "myntra" in url_lower:
        return _capture_myntra(url, out_path, viewport)
    
    # Extract domain from URL for homepage visit
    from urllib.parse import urlparse
    parsed_url = urlparse(url)
    domain = f"{parsed_url.scheme}://{parsed_url.netloc}"
    homepage_url = f"{domain}/"
    
    # Try multiple strategies to bypass access denied
    strategies = [
        lambda: _capture_with_homepage_first(url, homepage_url, out_path, viewport, strategy_name="Strategy 1"),
        lambda: _capture_with_mobile_ua(url, homepage_url, out_path, viewport, strategy_name="Strategy 2"),
        lambda: _capture_with_stealth(url, homepage_url, out_path, viewport, strategy_name="Strategy 3"),
        lambda: _capture_with_firefox(url, homepage_url, out_path, viewport, strategy_name="Strategy 4"),
    ]
    
    for strategy in strategies:
        try:
            result = strategy()
            # Verify screenshot is not access denied page
            if result and _verify_not_access_denied(result):
                return result
            else:
                print("Screenshot appears to be access denied page, trying next strategy...")
        except Exception as e:
            print(f"Strategy failed: {e}, trying next...")
            continue
    
    # If all strategies fail, return the last attempt
    print("Warning: All strategies failed, returning last attempt")
    return out_path


def _capture_with_homepage_first(url: str, homepage_url: str, out_path: str, viewport, strategy_name="Default"):
    """Capture with homepage visit first to establish session"""
    from playwright.sync_api import sync_playwright
    
    with sync_playwright() as p:
        browser_args = [
            '--disable-blink-features=AutomationControlled',
            '--disable-features=IsolateOrigins,site-per-process',
            '--disable-dev-shm-usage',
            '--no-sandbox',
            '--disable-setuid-sandbox',
            '--disable-web-security',
            '--disable-features=VizDisplayCompositor',
            '--disable-infobars',
            '--disable-notifications',
            '--window-size=1920,1080'
        ]
        
        browser = p.chromium.launch(headless=True, args=browser_args)
        
        context = browser.new_context(
            viewport={"width": viewport[0], "height": viewport[1]},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            locale="en-US",
            timezone_id="Asia/Kolkata",
            java_script_enabled=True,
            permissions=["geolocation"],
            geolocation={"latitude": 28.6139, "longitude": 77.2090},  # Delhi coordinates
        )
        
        page = context.new_page()
        
        # Advanced stealth script
        page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
            
            window.chrome = {
                runtime: {},
                loadTimes: function() {},
                csi: function() {},
                app: {}
            };
            
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5]
            });
            
            Object.defineProperty(navigator, 'languages', {
                get: () => ['en-US', 'en']
            });
            
            Object.defineProperty(navigator, 'connection', {
                get: () => ({
                    effectiveType: '4g',
                    rtt: 50,
                    downlink: 10,
                    saveData: false
                })
            });
            
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) => (
                parameters.name === 'notifications' ?
                    Promise.resolve({ state: Notification.permission }) :
                    originalQuery(parameters)
            );
            
            // Override getBattery if it exists
            if (navigator.getBattery) {
                navigator.getBattery = () => Promise.resolve({
                    charging: true,
                    chargingTime: 0,
                    dischargingTime: Infinity,
                    level: 1
                });
            }
        """)
        
        # Set comprehensive headers
        page.set_extra_http_headers({
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
            "Accept-Language": "en-US,en;q=0.9,hi;q=0.8",
            "Accept-Encoding": "gzip, deflate, br, zstd",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Cache-Control": "max-age=0",
            "DNT": "1",
            "Pragma": "no-cache"
        })
        
        # Step 1: Visit homepage first to establish session
        try:
            print(f"{strategy_name}: Visiting homepage first: {homepage_url}")
            page.goto(homepage_url, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(2000)  # Wait for session to establish
            
            # Scroll a bit to simulate human behavior
            page.evaluate("window.scrollTo(0, 300)")
            page.wait_for_timeout(1000)
            page.evaluate("window.scrollTo(0, 0)")
            page.wait_for_timeout(1000)
        except Exception as e:
            print(f"Homepage visit warning: {e}, continuing to product page...")
        
        # Step 2: Navigate to actual URL with proper referer
        page.set_extra_http_headers({
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br, zstd",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "same-origin",  # Changed from "none" since we're coming from homepage
            "Sec-Fetch-User": "?1",
            "Referer": homepage_url,  # Important: set referer to homepage
            "Cache-Control": "max-age=0",
            "DNT": "1"
        })
        
        # Navigate to target URL
        url_lower = url.lower()
        try:
            if "amazon" in url_lower:
                page.goto(url, wait_until="domcontentloaded", timeout=60000)
                page.wait_for_timeout(5000)
            elif "flipkart" in url_lower:
                page.goto(url, wait_until="networkidle", timeout=45000)
                page.wait_for_timeout(3000)
            elif "meesho" in url_lower:
                page.goto(url, wait_until="networkidle", timeout=40000)
                page.wait_for_timeout(3000)
            elif "ajio" in url_lower:
                # Ajio needs special handling
                page.goto(url, wait_until="domcontentloaded", timeout=60000)
                page.wait_for_timeout(4000)
                # Scroll to trigger lazy loading
                page.evaluate("window.scrollTo(0, 500)")
                page.wait_for_timeout(2000)
                page.evaluate("window.scrollTo(0, 0)")
                page.wait_for_timeout(1000)
            else:
                try:
                    page.goto(url, wait_until="networkidle", timeout=40000)
                    page.wait_for_timeout(3000)
                except:
                    page.goto(url, wait_until="domcontentloaded", timeout=60000)
                    page.wait_for_timeout(4000)
        except Exception as e:
            print(f"Navigation warning: {e}")
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=60000)
                page.wait_for_timeout(3000)
            except:
                pass
        
        # Check for access denied
        page_text = page.inner_text("body").lower()
        if "access denied" in page_text or "you don't have permission" in page_text:
            raise Exception("Access denied detected")
        
        page.wait_for_timeout(2000)
        
        # Take screenshot
        page.screenshot(path=out_path, full_page=True)
        browser.close()
        return out_path


def _capture_with_mobile_ua(url: str, homepage_url: str, out_path: str, viewport, strategy_name="Mobile"):
    """Capture with mobile user agent (often bypasses bot detection)"""
    from playwright.sync_api import sync_playwright
    
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=['--disable-blink-features=AutomationControlled', '--no-sandbox', '--disable-setuid-sandbox']
        )
        
        context = browser.new_context(
            viewport={"width": 390, "height": 844},
            user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1",
            locale="en-IN",
            timezone_id="Asia/Kolkata",
            device_scale_factor=2,
            is_mobile=True,
            has_touch=True
        )
        
        page = context.new_page()
        page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
        """)
        
        page.set_extra_http_headers({
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-IN,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Referer": homepage_url
        })
        
        try:
            page.goto(homepage_url, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(2000)
        except:
            pass
        
        page.goto(url, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(4000)
        
        page_text = page.inner_text("body").lower()
        if "access denied" in page_text or "you don't have permission" in page_text:
            raise Exception("Access denied detected")
        
        page.screenshot(path=out_path, full_page=True)
        browser.close()
        return out_path


def _capture_with_stealth(url: str, homepage_url: str, out_path: str, viewport, strategy_name="Stealth"):
    """Capture with maximum stealth settings"""
    from playwright.sync_api import sync_playwright
    
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-features=IsolateOrigins,site-per-process',
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-dev-shm-usage'
            ]
        )
        
        context = browser.new_context(
            viewport={"width": viewport[0], "height": viewport[1]},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0",
            locale="en-IN",
            timezone_id="Asia/Kolkata",
            java_script_enabled=True,
            geolocation={"latitude": 28.6139, "longitude": 77.2090},
            permissions=["geolocation"]
        )
        
        page = context.new_page()
        
        # Maximum stealth script
        page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => false });
            
            window.chrome = {
                runtime: {},
                loadTimes: function() {},
                csi: function() {},
                app: {}
            };
            
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5]
            });
            
            Object.defineProperty(navigator, 'languages', {
                get: () => ['en-US', 'en']
            });
            
            Object.defineProperty(navigator, 'connection', {
                get: () => ({
                    effectiveType: '4g',
                    rtt: 50,
                    downlink: 10
                })
            });
        """)
        
        page.set_extra_http_headers({
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-IN,en;q=0.9,en-US;q=0.8",
            "Accept-Encoding": "gzip, deflate, br, zstd",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Referer": homepage_url
        })
        
        try:
            page.goto(homepage_url, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(2000)
        except:
            pass
        
        page.goto(url, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(4000)
        
        page_text = page.inner_text("body").lower()
        if "access denied" in page_text or "you don't have permission" in page_text:
            raise Exception("Access denied detected")
        
        page.screenshot(path=out_path, full_page=True)
        browser.close()
        return out_path


def _capture_with_firefox(url: str, homepage_url: str, out_path: str, viewport, strategy_name="Firefox"):
    """Capture using Firefox (different fingerprint)"""
    from playwright.sync_api import sync_playwright
    
    try:
        with sync_playwright() as p:
            browser = p.firefox.launch(headless=True)
            
            context = browser.new_context(
                viewport={"width": viewport[0], "height": viewport[1]},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:131.0) Gecko/20100101 Firefox/131.0",
                locale="en-IN",
                timezone_id="Asia/Kolkata"
            )
            
            page = context.new_page()
            page.set_extra_http_headers({
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-IN,en;q=0.9",
                "Accept-Encoding": "gzip, deflate, br",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
                "Referer": homepage_url
            })
            
            try:
                page.goto(homepage_url, wait_until="domcontentloaded", timeout=30000)
                page.wait_for_timeout(2000)
            except:
                pass
            
            page.goto(url, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(5000)
            
            page_text = page.inner_text("body").lower()
            if "access denied" in page_text or "you don't have permission" in page_text:
                raise Exception("Access denied detected")
            
            page.screenshot(path=out_path, full_page=True)
            browser.close()
            return out_path
    except Exception as e:
        raise Exception(f"Firefox not available: {e}")


def _verify_not_access_denied(file_path: str) -> bool:
    """Check if screenshot is NOT an access denied page"""
    try:
        from PIL import Image
        import pytesseract
        
        # Quick OCR check on screenshot
        img = Image.open(file_path)
        text = pytesseract.image_to_string(img, lang='eng').lower()
        
        # Check for access denied indicators
        denied_indicators = [
            "access denied",
            "you don't have permission",
            "reference #",
            "errors.edgesuite.net"
        ]
        
        for indicator in denied_indicators:
            if indicator in text:
                return False
        
        return True
    except Exception as e:
        print(f"Could not verify screenshot: {e}")
        return True  # Assume valid if we can't check


def _capture_myntra(url: str, out_path: str, viewport=(1280, 2000)):
    """
    Special handler for Myntra with multiple fallback strategies.
    Myntra has strong bot detection, so we try different approaches.
    """
    print("Using Myntra-specific capture strategy...")
    
    strategies = [
        # Strategy 1: Non-headless mode (more realistic, slower but works better)
        lambda: _try_myntra_non_headless(url, out_path, viewport),
        # Strategy 2: Mobile user agent (often bypasses bot detection)
        lambda: _try_myntra_mobile(url, out_path, viewport),
        # Strategy 3: Chromium with stealth mode and homepage first
        lambda: _try_myntra_chromium_stealth(url, out_path, viewport),
        # Strategy 4: Firefox (sometimes works better)
        lambda: _try_myntra_firefox(url, out_path, viewport),
        # Strategy 5: Chromium with different settings
        lambda: _try_myntra_chromium_alt(url, out_path, viewport),
    ]
    
    for i, strategy in enumerate(strategies, 1):
        try:
            print(f"Trying Myntra strategy {i}...")
            result = strategy()
            # Verify screenshot is not blank
            if result and _verify_screenshot_not_blank(result):
                print(f"Myntra screenshot captured successfully with strategy {i}")
                return result
            else:
                print(f"Strategy {i} produced blank screenshot, trying next...")
        except Exception as e:
            print(f"Strategy {i} failed: {e}")
            continue
    
    # If all fail, return the last attempted path (might be empty but file exists)
    print("Warning: All Myntra strategies failed, screenshot may be blank")
    return out_path


def _verify_screenshot_not_blank(file_path: str, min_content_pixels: int = 1000) -> bool:
    """Check if screenshot has actual content (not just white/blank)"""
    try:
        from PIL import Image
        
        # Try numpy first (usually available with easyocr)
        try:
            import numpy as np
            
            img = Image.open(file_path)
            img_array = np.array(img)
            
            # Convert to grayscale if needed
            if len(img_array.shape) == 3:
                gray = np.mean(img_array, axis=2)
            else:
                gray = img_array
            
            # Count non-white pixels (assuming white is close to 255)
            non_white = np.sum(gray < 240)  # Threshold for "not white"
            
            return non_white > min_content_pixels
        except ImportError:
            # Fallback: simple check using PIL only
            img = Image.open(file_path)
            pixels = list(img.getdata())
            
            # Count non-white pixels (RGB values close to 255,255,255)
            non_white = sum(1 for p in pixels[:10000] if sum(p[:3] if isinstance(p, tuple) else [p]) < 720)
            # Sample first 10000 pixels for speed
            
            return non_white > (min_content_pixels // 10)  # Adjusted threshold for sample
    except Exception as e:
        print(f"Could not verify screenshot: {e}")
        return True  # Assume valid if we can't check


def _try_myntra_chromium_stealth(url: str, out_path: str, viewport=(1280, 2000)):
    """Try Myntra with Chromium using advanced stealth techniques"""
    from playwright.sync_api import sync_playwright
    
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-features=IsolateOrigins,site-per-process',
                '--disable-dev-shm-usage',
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-web-security',
                '--disable-gpu',
                '--disable-software-rasterizer',
                '--window-size=1920,1080'
            ]
        )
        
        context = browser.new_context(
            viewport={"width": viewport[0], "height": viewport[1]},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0",
            locale="en-IN",
            timezone_id="Asia/Kolkata",
            java_script_enabled=True,
            # Add geolocation for India
            geolocation={"latitude": 28.6139, "longitude": 77.2090},  # Delhi coordinates
            permissions=["geolocation"]
        )
        
        page = context.new_page()
        
        # Advanced stealth scripts
        page.add_init_script("""
            // Remove webdriver
            Object.defineProperty(navigator, 'webdriver', {
                get: () => false
            });
            
            // Override chrome
            window.chrome = {
                runtime: {},
                loadTimes: function() {},
                csi: function() {},
                app: {}
            };
            
            // Override plugins
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5]
            });
            
            // Override languages
            Object.defineProperty(navigator, 'languages', {
                get: () => ['en-US', 'en']
            });
            
            // Add connection property
            Object.defineProperty(navigator, 'connection', {
                get: () => ({
                    effectiveType: '4g',
                    rtt: 50,
                    downlink: 10
                })
            });
            
            // Override permissions
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) => (
                parameters.name === 'notifications' ?
                    Promise.resolve({ state: Notification.permission }) :
                    originalQuery(parameters)
            );
        """)
        
        page.set_extra_http_headers({
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "en-IN,en;q=0.9,en-US;q=0.8",
            "Accept-Encoding": "gzip, deflate, br, zstd",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Cache-Control": "max-age=0",
            "DNT": "1",
            "Referer": "https://www.myntra.com/"
        })
        
        # Navigate slowly to mimic human behavior
        try:
            # First, visit homepage to establish session (helps bypass bot detection)
            try:
                page.goto("https://www.myntra.com/", wait_until="domcontentloaded", timeout=30000)
                page.wait_for_timeout(2000)
            except:
                pass  # Continue even if homepage fails
            
            # Now navigate to product page
            # Try with commit first (faster, less blocking)
            try:
                page.goto(url, wait_until="commit", timeout=60000)
            except:
                # Fallback to domcontentloaded
                page.goto(url, wait_until="domcontentloaded", timeout=60000)
            
            page.wait_for_timeout(3000)
            
            # Wait for content to load
            try:
                page.wait_for_selector("body", timeout=10000)
            except:
                pass
            
            # Check if page actually loaded (not blank)
            try:
                body_text = page.evaluate("document.body ? document.body.innerText : ''")
                if not body_text or len(body_text.strip()) < 10:
                    # Page might be blank, wait more
                    page.wait_for_timeout(3000)
                    body_text = page.evaluate("document.body ? document.body.innerText : ''")
                    if not body_text or len(body_text.strip()) < 10:
                        raise Exception("Page appears to be blank or blocked")
            except:
                pass
            
            # Scroll slowly to trigger lazy loading
            page.evaluate("""
                window.scrollTo({
                    top: 300,
                    behavior: 'smooth'
                });
            """)
            page.wait_for_timeout(2000)
            
            page.evaluate("window.scrollTo({top: 0, behavior: 'smooth'});")
            page.wait_for_timeout(1000)
            
        except Exception as e:
            print(f"Myntra navigation warning: {e}")
            # Continue anyway, might have partial page
        
        # Wait for any remaining content
        page.wait_for_timeout(2000)
        
        # Take screenshot
        page.screenshot(path=out_path, full_page=True)
        browser.close()
        return out_path


def _try_myntra_firefox(url: str, out_path: str, viewport=(1280, 2000)):
    """Try Myntra with Firefox (sometimes bypasses detection better)"""
    from playwright.sync_api import sync_playwright
    
    try:
        with sync_playwright() as p:
            # Check if Firefox is available
            try:
                browser = p.firefox.launch(headless=True)
            except Exception as e:
                raise Exception(f"Firefox not available: {e}")
            
            context = browser.new_context(
                viewport={"width": viewport[0], "height": viewport[1]},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:131.0) Gecko/20100101 Firefox/131.0",
                locale="en-IN",
                timezone_id="Asia/Kolkata"
            )
            
            page = context.new_page()
            page.set_extra_http_headers({
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-IN,en;q=0.9",
                "Accept-Encoding": "gzip, deflate, br",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
                "Referer": "https://www.myntra.com/"
            })
            
            page.goto(url, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(5000)
            page.screenshot(path=out_path, full_page=True)
            browser.close()
            return out_path
    except Exception as e:
        raise Exception(f"Firefox strategy failed: {e}")


def _try_myntra_mobile(url: str, out_path: str, viewport=(1280, 2000)):
    """Try Myntra with mobile user agent (mobile sites often have less bot detection)"""
    from playwright.sync_api import sync_playwright
    
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--no-sandbox',
                '--disable-setuid-sandbox'
            ]
        )
        
        # Use mobile viewport and user agent
        context = browser.new_context(
            viewport={"width": 390, "height": 844},  # iPhone 12 Pro size
            user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1",
            locale="en-IN",
            timezone_id="Asia/Kolkata",
            device_scale_factor=2,
            is_mobile=True,
            has_touch=True
        )
        
        page = context.new_page()
        
        page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
        """)
        
        page.set_extra_http_headers({
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-IN,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Referer": "https://www.myntra.com/"
        })
        
        try:
            # Visit homepage first to establish session
            try:
                page.goto("https://www.myntra.com/", wait_until="domcontentloaded", timeout=30000)
                page.wait_for_timeout(2000)
            except:
                pass
            
            # Now navigate to product page
            page.goto(url, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(4000)
            
            # Check if content loaded
            content_check = page.evaluate("document.body && document.body.innerText ? document.body.innerText.length : 0")
            if content_check < 50:
                page.wait_for_timeout(3000)
            
            page.screenshot(path=out_path, full_page=True)
        except Exception as e:
            print(f"Mobile strategy error: {e}")
            try:
                page.screenshot(path=out_path, full_page=False)
            except:
                raise
        
        browser.close()
        return out_path


def _try_myntra_non_headless(url: str, out_path: str, viewport=(1280, 2000)):
    """Try Myntra with non-headless browser (most realistic, but slower)"""
    from playwright.sync_api import sync_playwright
    import os
    
    # Only use non-headless if not in headless environment
    # On Windows with display, this will show browser window briefly
    use_headless = os.environ.get('PLAYWRIGHT_HEADLESS', 'true').lower() == 'true'
    
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=use_headless,  # Set to False to see browser (slower but more realistic)
            args=[
                '--disable-blink-features=AutomationControlled',
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--start-maximized'
            ]
        )
        
        context = browser.new_context(
            viewport={"width": viewport[0], "height": viewport[1]},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            locale="en-IN",
            timezone_id="Asia/Kolkata"
        )
        
        page = context.new_page()
        
        page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => false });
            window.chrome = { runtime: {} };
        """)
        
        page.set_extra_http_headers({
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-IN,en;q=0.9",
            "Referer": "https://www.myntra.com/"
        })
        
        # Navigate to homepage first to establish session
        try:
            page.goto("https://www.myntra.com/", wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(2000)
        
            # Now navigate to product page
            page.goto(url, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(5000)
            
            # Verify content
            content_length = page.evaluate("document.body ? document.body.innerText.length : 0")
            if content_length < 100:
                page.wait_for_timeout(3000)
            
            page.screenshot(path=out_path, full_page=True)
        except Exception as e:
            print(f"Non-headless strategy error: {e}")
            try:
                page.screenshot(path=out_path, full_page=False)
            except:
                raise
        
        browser.close()
        return out_path


def _try_myntra_chromium_alt(url: str, out_path: str, viewport=(1280, 2000)):
    """Alternative Chromium strategy with minimal settings"""
    from playwright.sync_api import sync_playwright
    
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=['--no-sandbox', '--disable-setuid-sandbox']
        )
        
        context = browser.new_context(
            viewport={"width": viewport[0], "height": viewport[1]},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
        )
        
        page = context.new_page()
        
        try:
            page.goto(url, wait_until="load", timeout=60000)
            page.wait_for_timeout(5000)
            page.screenshot(path=out_path, full_page=True)
        except:
            page.screenshot(path=out_path, full_page=False)
        
        browser.close()
    return out_path

if __name__ == "__main__":
    url = "https://www.meesho.com/example-product-url"   # replace
    p = capture_fullpage(url, "product_page.png")
    print("Saved:", p)

