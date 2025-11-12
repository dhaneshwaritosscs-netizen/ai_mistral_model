from playwright.sync_api import sync_playwright
from PIL import Image
import io
import time


def _close_popups(page):
    """
    Close ALL popups/modals that appear anywhere on the page (top, bottom, center, etc.).
    Tries multiple comprehensive strategies to remove all popups before taking screenshot.
    """
    try:
        # Wait a bit for popups to appear
        page.wait_for_timeout(1500)
        
        # Strategy 1: Use JavaScript to find and close ALL popups comprehensively
        try:
            closed_count = page.evaluate("""
                (() => {
                    let closed_count = 0;
                    
                    // Find all possible popup/modal/overlay elements by various patterns
                    const popupSelectors = [
                        // Common popup/modal classes
                        '[class*="popup" i]',
                        '[class*="modal" i]',
                        '[class*="overlay" i]',
                        '[class*="cookie" i]',
                        '[class*="banner" i]',
                        '[class*="notification" i]',
                        '[class*="consent" i]',
                        '[class*="dialog" i]',
                        '[class*="drawer" i]',
                        '[class*="slideout" i]',
                        '[class*="toast" i]',
                        '[class*="alert" i]',
                        '[id*="popup" i]',
                        '[id*="modal" i]',
                        '[id*="cookie" i]',
                        '[id*="banner" i]',
                        '[id*="consent" i]',
                        '[id*="notification" i]',
                        // Fixed position elements that might be popups
                        '[style*="position: fixed"]',
                        '[style*="position:fixed"]',
                        '[style*="z-index"]',
                        // Common cookie consent patterns
                        '[class*="cookie-consent"]',
                        '[class*="cookie-banner"]',
                        '[class*="gdpr"]',
                        '[class*="cc-banner"]',
                        '[class*="cookie-notice"]',
                    ];
                    
                    const allPopups = new Set();
                    
                    // Collect all popup elements
                    popupSelectors.forEach(selector => {
                        try {
                            document.querySelectorAll(selector).forEach(el => {
                                const style = window.getComputedStyle(el);
                                const rect = el.getBoundingClientRect();
                                
                                // Check if element is visible and positioned like a popup
                                if (style.display !== 'none' && 
                                    style.visibility !== 'hidden' && 
                                    style.opacity !== '0' &&
                                    rect.width > 50 && 
                                    rect.height > 50) {
                                    allPopups.add(el);
                                }
                            });
                        } catch(e) {}
                    });
                    
                    // Also find elements with high z-index that might be overlays
                    document.querySelectorAll('*').forEach(el => {
                        try {
                            const style = window.getComputedStyle(el);
                            const zIndex = parseInt(style.zIndex) || 0;
                            const position = style.position;
                            const rect = el.getBoundingClientRect();
                            
                            // High z-index fixed/sticky elements are likely popups
                            if ((position === 'fixed' || position === 'sticky') &&
                                zIndex > 100 &&
                                rect.width > 100 && 
                                rect.height > 50) {
                                allPopups.add(el);
                            }
                        } catch(e) {}
                    });
                    
                    // Try to close each popup by finding close buttons first
                    allPopups.forEach(popup => {
                        try {
                            // Look for close buttons within the popup
                            let closeButtons = Array.from(popup.querySelectorAll(
                                'button[aria-label*="close" i], ' +
                                'button[class*="close" i], ' +
                                '[class*="close" i][class*="button" i], ' +
                                '[data-testid*="close" i], ' +
                                '.close, .close-btn, .close-button, .modal-close, .popup-close'
                            ));
                            
                            // Also check for buttons with X text
                            popup.querySelectorAll('button').forEach(btn => {
                                const text = btn.textContent || btn.innerText || '';
                                if (text.trim() === '×' || text.trim() === '✕' || text.trim() === 'X' || text.trim() === 'x') {
                                    closeButtons.push(btn);
                                }
                            });
                            
                            let popup_closed = false;
                            closeButtons.forEach(btn => {
                                try {
                                    const btnStyle = window.getComputedStyle(btn);
                                    if (btnStyle.display !== 'none' && btnStyle.visibility !== 'hidden') {
                                        btn.click();
                                        popup_closed = true;
                                    }
                                } catch(e) {}
                            });
                            
                            // If no close button found, try clicking action buttons
                            if (!popup_closed) {
                                const actionTexts = ['ALLOW ALL', 'Allow All', 'ALLOW', 'ACCEPT', 'Accept', 'ACCEPT ALL', 
                                                    'AGREE', 'Agree', 'OK', 'Got it', 'I understand', 'Continue', 
                                                    'CONTINUE', 'GO SHOPPING', 'DENY', 'Deny', 'REJECT', 'Reject'];
                                
                                let actionButtons = Array.from(popup.querySelectorAll(
                                    '[class*="accept" i], ' +
                                    '[class*="allow" i], ' +
                                    '[class*="agree" i], ' +
                                    '[class*="deny" i], ' +
                                    '[class*="reject" i]'
                                ));
                                
                                // Also find buttons with action text
                                popup.querySelectorAll('button').forEach(btn => {
                                    const text = (btn.textContent || btn.innerText || '').trim();
                                    if (actionTexts.some(actionText => text.includes(actionText))) {
                                        actionButtons.push(btn);
                                    }
                                });
                                
                                actionButtons.forEach(btn => {
                                    try {
                                        const btnStyle = window.getComputedStyle(btn);
                                        if (btnStyle.display !== 'none' && btnStyle.visibility !== 'hidden') {
                                            btn.click();
                                            popup_closed = true;
                                            return;
                                        }
                                    } catch(e) {}
                                });
                            }
                            
                            // If still not closed, hide it directly
                            if (!popup_closed && popup.style) {
                                popup.style.display = 'none';
                                popup.style.visibility = 'hidden';
                                popup_closed = true;
                            }
                            
                            if (popup_closed) {
                                closed_count++;
                            }
                        } catch(e) {}
                    });
                    
                    return closed_count;
                })()
            """)
            
            if closed_count > 0:
                print(f"Closed {closed_count} popup(s) using JavaScript")
                page.wait_for_timeout(500)
        except Exception as e:
            print(f"JavaScript popup closing warning: {e}")
        
        # Strategy 2: Press ESC key multiple times (closes most modals)
        try:
            for _ in range(3):
                page.keyboard.press("Escape")
                page.wait_for_timeout(300)
        except:
            pass
        
        # Strategy 3: Click ALL close buttons (not just first one)
        close_selectors = [
            # Common close button patterns
            'button[aria-label*="close" i]',
            'button[aria-label*="Close" i]',
            'button[aria-label*="CLOSE" i]',
            '[class*="modal-close"]',
            '[class*="popup-close"]',
            '[class*="close-button"]',
            '[id*="close" i]',
            '[id*="Close" i]',
            '[class*="icon-close"]',
            '[class*="IconClose"]',
            # SVG close icons
            'svg[class*="close" i]',
            'svg[aria-label*="close" i]',
            # Specific common patterns
            '[data-testid*="close" i]',
            '[data-testid*="Close" i]',
            '.close-icon',
            '.close-btn',
            '.modal-close-btn',
            '.popup-close-btn',
        ]
        
        # Click all matching close buttons (not just first)
        for selector in close_selectors:
            try:
                elements = page.query_selector_all(selector)
                for element in elements:
                    try:
                        is_visible = page.evaluate(f"""
                            (() => {{
                                const el = arguments[0];
                                if (!el) return false;
                                const style = window.getComputedStyle(el);
                                return style.display !== 'none' && 
                                       style.visibility !== 'hidden' && 
                                       style.opacity !== '0' &&
                                       el.offsetParent !== null;
                            }})()
                        """, element)
                        
                        if is_visible:
                            element.click(timeout=1000)
                            page.wait_for_timeout(300)
                            print(f"Closed popup using selector: {selector}")
                    except:
                        continue
            except:
                continue
        
        # Also try to find buttons with X text using locator
        try:
            x_texts = ['×', '✕', 'X', 'x']
            for x_text in x_texts:
                try:
                    # Try to click all X buttons, not just first
                    buttons = page.locator(f'button:has-text("{x_text}")').all()
                    for btn in buttons:
                        try:
                            if btn.is_visible():
                                btn.click(timeout=1000)
                                page.wait_for_timeout(300)
                                print(f"Closed popup using X button with text: {x_text}")
                        except:
                            continue
                except:
                    continue
        except:
            pass
        
        # Strategy 4: Click action buttons (Accept, Allow, Deny, etc.) - click ALL of them
        try:
            action_texts = [
                "ALLOW ALL", "Allow All", "ALLOW", "Allow",
                "ACCEPT", "Accept", "ACCEPT ALL", "Accept All",
                "AGREE", "Agree", "I AGREE", "I Agree",
                "OK", "Got it", "I understand", "I Understand",
                "Continue", "CONTINUE", "GO SHOPPING", "Go Shopping",
                "DENY", "Deny", "REJECT", "Reject",
                "CUSTOMIZE", "Customize", "ALLOW SELECTION", "Allow Selection"
            ]
            
            for text in action_texts:
                try:
                    # Click ALL buttons with this text, not just first
                    buttons = page.locator(f'button:has-text("{text}")').all()
                    for btn in buttons:
                        try:
                            if btn.is_visible():
                                btn.click(timeout=1000)
                                page.wait_for_timeout(500)
                                print(f"Clicked action button with text: {text}")
                        except:
                            continue
                except:
                    continue
            
            # Also try class-based selectors
            action_selectors = [
                '[class*="continue-button"]',
                '[class*="go-shopping"]',
                '[class*="accept"]',
                '[class*="allow"]',
                '[class*="agree"]',
                '[class*="deny"]',
                '[class*="reject"]',
            ]
            
            for selector in action_selectors:
                try:
                    elements = page.query_selector_all(selector)
                    for element in elements:
                        try:
                            is_visible = page.evaluate(f"""
                                (() => {{
                                    const el = arguments[0];
                                    if (!el) return false;
                                    const style = window.getComputedStyle(el);
                                    return style.display !== 'none' && 
                                           style.visibility !== 'hidden';
                                }})()
                            """, element)
                            if is_visible:
                                element.click(timeout=1000)
                                page.wait_for_timeout(500)
                                print(f"Clicked action button: {selector}")
                        except:
                            continue
                except:
                    continue
        except:
            pass
        
        # Strategy 5: Click outside modal/overlay (backdrop click) - try all overlays
        try:
            overlay_selectors = [
                '[class*="overlay" i]',
                '[class*="backdrop" i]',
                '[class*="modal-overlay" i]',
                '[class*="popup-overlay" i]',
                '[class*="modal-backdrop" i]',
            ]
            
            for selector in overlay_selectors:
                try:
                    elements = page.query_selector_all(selector)
                    for element in elements:
                        try:
                            box = element.bounding_box()
                            if box and box['width'] > 100 and box['height'] > 100:
                                # Click at center of overlay (usually closes modal)
                                page.mouse.click(box['x'] + box['width'] / 2, box['y'] + box['height'] / 2)
                                page.wait_for_timeout(300)
                                print(f"Clicked overlay to close popup: {selector}")
                        except:
                            continue
                except:
                    continue
        except:
            pass
        
        # Strategy 6: Final cleanup - hide any remaining fixed position elements that might be popups
        try:
            page.evaluate("""
                // Find and hide any remaining fixed/sticky elements with high z-index
                document.querySelectorAll('*').forEach(el => {
                    try {
                        const style = window.getComputedStyle(el);
                        const position = style.position;
                        const zIndex = parseInt(style.zIndex) || 0;
                        const rect = el.getBoundingClientRect();
                        
                        // Hide fixed/sticky elements that look like popups
                        if ((position === 'fixed' || position === 'sticky') &&
                            zIndex > 500 &&
                            rect.width > 200 && 
                            rect.height > 100 &&
                            style.display !== 'none') {
                            
                            // Check if it's a cookie/popup related element
                            const className = el.className?.toLowerCase() || '';
                            const id = el.id?.toLowerCase() || '';
                            
                            if (className.includes('cookie') || 
                                className.includes('popup') || 
                                className.includes('modal') || 
                                className.includes('banner') ||
                                className.includes('consent') ||
                                className.includes('notification') ||
                                id.includes('cookie') ||
                                id.includes('popup') ||
                                id.includes('modal') ||
                                id.includes('banner') ||
                                id.includes('consent')) {
                                el.style.display = 'none';
                                el.style.visibility = 'hidden';
                            }
                        }
                    } catch(e) {}
                });
            """)
            page.wait_for_timeout(300)
        except:
            pass
        
        # Final wait to ensure all popups are closed
        page.wait_for_timeout(800)
        
        # Final check: Press ESC one more time
        try:
            page.keyboard.press("Escape")
            page.wait_for_timeout(300)
        except:
            pass
        
    except Exception as e:
        print(f"Popup closing warning: {e}")
        # Continue even if popup closing fails - still try to take screenshot


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
        
        #  use playwright chrome on headless mode (to open up the browser and see the popup)
        browser = p.chromium.launch(headless=True, args=browser_args)
        # browser = p.chromium.launch(channel="chrome", headless=False)
        
        
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
        
        # Close any popups before taking screenshot
        _close_popups(page)
        
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
        
        # Close any popups before taking screenshot
        _close_popups(page)
        
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
        
        # Close any popups before taking screenshot
        _close_popups(page)
        
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
            
            # Close any popups before taking screenshot
            _close_popups(page)
            
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
        
        # Close any popups before taking screenshot
        _close_popups(page)
        
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
            
            # Close any popups before taking screenshot
            _close_popups(page)
            
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
            
            # Close any popups before taking screenshot
            _close_popups(page)
            
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
            
            # Close any popups before taking screenshot
            _close_popups(page)
            
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
            
            # Close any popups before taking screenshot
            _close_popups(page)
            
            page.screenshot(path=out_path, full_page=True)
        except:
            # Close any popups even if navigation failed
            try:
                _close_popups(page)
            except:
                pass
            page.screenshot(path=out_path, full_page=False)
        
        browser.close()
    return out_path

if __name__ == "__main__":
    url = "https://www.meesho.com/example-product-url"   # replace
    p = capture_fullpage(url, "product_page.png")
    print("Saved:", p)


