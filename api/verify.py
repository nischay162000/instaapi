from flask import Flask, request, jsonify
from flask_cors import CORS
import sys
import os
import random
import logging
import time
import requests

# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(__file__))

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})
app.config['JSON_SORT_KEYS'] = False

try:
    from instagrapi import Client
    from instagrapi.exceptions import (
        BadPassword, 
        UserNotFound, 
        TwoFactorRequired,
        ChallengeRequired, 
        PleaseWaitFewMinutes, 
        RateLimitError,
        LoginRequired
    )
    INSTAGRAPI_AVAILABLE = True
except ImportError:
    INSTAGRAPI_AVAILABLE = False
    print("Warning: instagrapi not available")

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Proxy configuration
class ProxyManager:
    def __init__(self):
        self.proxies = []
        self.failed_proxies = set()
        self.last_used = {}
        self.last_fetch = 0
        self._load_proxies()
        
    def _fetch_free_proxies(self):
        """Fetch free proxies from public APIs"""
        proxies = []
        
        try:
            # ProxyScrape API - Free HTTPS proxies
            logger.info("Fetching free proxies from ProxyScrape...")
            response = requests.get(
                "https://api.proxyscrape.com/v2/?request=displayproxies&protocol=http&timeout=10000&country=all&ssl=all&anonymity=all",
                timeout=10
            )
            if response.status_code == 200:
                proxy_list = response.text.strip().split('\n')
                for proxy in proxy_list[:20]:  # Get first 20
                    if proxy.strip():
                        proxies.append(f"http://{proxy.strip()}")
                logger.info(f"Fetched {len(proxies)} proxies from ProxyScrape")
        except Exception as e:
            logger.error(f"Failed to fetch from ProxyScrape: {e}")
        
        try:
            # GeoNode API - Free proxies
            logger.info("Fetching proxies from GeoNode...")
            response = requests.get(
                "https://proxylist.geonode.com/api/proxy-list?limit=20&page=1&sort_by=lastChecked&sort_type=desc&protocols=http,https",
                timeout=10
            )
            if response.status_code == 200:
                data = response.json()
                for item in data.get('data', [])[:10]:
                    ip = item.get('ip')
                    port = item.get('port')
                    if ip and port:
                        proxies.append(f"http://{ip}:{port}")
                logger.info(f"Total proxies after GeoNode: {len(proxies)}")
        except Exception as e:
            logger.error(f"Failed to fetch from GeoNode: {e}")
        
        try:
            # Proxy-list.download
            logger.info("Fetching proxies from proxy-list.download...")
            response = requests.get(
                "https://www.proxy-list.download/api/v1/get?type=http",
                timeout=10
            )
            if response.status_code == 200:
                proxy_list = response.text.strip().split('\n')
                for proxy in proxy_list[:10]:
                    if proxy.strip():
                        proxies.append(f"http://{proxy.strip()}")
                logger.info(f"Total proxies after proxy-list: {len(proxies)}")
        except Exception as e:
            logger.error(f"Failed to fetch from proxy-list: {e}")
        
        return proxies
    
    def _load_proxies(self):
        """Load proxies from environment or fetch free ones"""
        proxies = []
        
        # Check if we should fetch new proxies (every 30 minutes)
        current_time = time.time()
        should_fetch = (current_time - self.last_fetch) > 1800
        
        # Single proxy from environment
        single_proxy = os.getenv('PROXY_URL')
        if single_proxy:
            proxies.append(single_proxy)
            logger.info("Using configured proxy from PROXY_URL")
        
        # Multiple proxies (comma-separated)
        proxy_list = os.getenv('PROXY_LIST')
        if proxy_list:
            proxies.extend([p.strip() for p in proxy_list.split(',') if p.strip()])
            logger.info(f"Loaded {len(proxies)} proxies from PROXY_LIST")
        
        # If no proxies configured or need refresh, fetch free ones
        if (not proxies or should_fetch) and os.getenv('USE_FREE_PROXIES', 'true').lower() == 'true':
            logger.info("Fetching free proxies...")
            free_proxies = self._fetch_free_proxies()
            proxies.extend(free_proxies)
            self.last_fetch = current_time
        
        if proxies:
            self.proxies = list(set(proxies))  # Remove duplicates
            logger.info(f"Total {len(self.proxies)} unique proxies available")
        else:
            logger.warning("No proxies available - using direct connection (may be blocked by Instagram)")
        
        return proxies
    
    def get_proxy(self):
        """Get a working proxy with rate limiting"""
        # Refresh proxies if empty
        if not self.proxies:
            self._load_proxies()
        
        if not self.proxies:
            return None
        
        # Filter out failed proxies
        available = [p for p in self.proxies if p not in self.failed_proxies]
        
        if not available:
            # Reset if all proxies failed
            logger.warning("All proxies failed, fetching new ones...")
            self.failed_proxies.clear()
            self._load_proxies()
            available = self.proxies.copy()
        
        if not available:
            return None
        
        # Rate limiting: Don't use same proxy within 10 seconds
        current_time = time.time()
        available = [
            p for p in available 
            if current_time - self.last_used.get(p, 0) > 10
        ]
        
        if not available:
            # If all were used recently, pick least recently used
            available = sorted(
                [p for p in self.proxies if p not in self.failed_proxies], 
                key=lambda p: self.last_used.get(p, 0)
            )[:3]
        
        if not available:
            return None
        
        proxy = random.choice(available)
        self.last_used[proxy] = current_time
        logger.info(f"Using proxy: {proxy}")
        return proxy
    
    def mark_failed(self, proxy):
        """Mark a proxy as failed"""
        if proxy:
            self.failed_proxies.add(proxy)
            logger.warning(f"Marked proxy as failed: {proxy}")
            
            # If too many failures, refresh proxy list
            if len(self.failed_proxies) > len(self.proxies) * 0.7:
                logger.info("Too many failed proxies, refreshing list...")
                self.last_fetch = 0  # Force refresh on next get_proxy call

# Initialize proxy manager
proxy_manager = ProxyManager()

def get_android_device():
    """Generate realistic Android device settings"""
    devices = [
        {
            "app_version": "269.0.0.18.75",
            "android_version": 33,
            "android_release": "13.0",
            "dpi": "480dpi",
            "resolution": "1080x2400",
            "manufacturer": "Samsung",
            "device": "SM-S908B",
            "model": "Galaxy S22 Ultra",
            "cpu": "exynos2200"
        },
        {
            "app_version": "268.0.0.18.75",
            "android_version": 31,
            "android_release": "12.0",
            "dpi": "420dpi",
            "resolution": "1080x2340",
            "manufacturer": "Xiaomi",
            "device": "2201123G",
            "model": "Redmi Note 11 Pro",
            "cpu": "mt6877"
        },
        {
            "app_version": "269.0.0.18.75",
            "android_version": 33,
            "android_release": "13.0",
            "dpi": "560dpi",
            "resolution": "1440x3200",
            "manufacturer": "OnePlus",
            "device": "OP5913L1",
            "model": "OnePlus 11",
            "cpu": "qcom"
        }
    ]
    return random.choice(devices)

def check_instagram_login(username, password, verification_code=None):
    """Check Instagram login credentials with proxy rotation"""
    
    if not INSTAGRAPI_AVAILABLE:
        return {
            "success": False,
            "message": "Instagram API library not available",
            "user_info": None,
            "requires_2fa": False
        }
    
    result = {
        "success": False,
        "message": "",
        "user_info": None,
        "requires_2fa": False
    }

    cl = None
    proxy_used = None
    max_retries = 3
    
    for attempt in range(max_retries):
        try:
            cl = Client()
            device = get_android_device()
            cl.set_device(device)

            user_agent = (
                f"Instagram {device['app_version']} Android "
                f"({device['android_version']}/{device['android_release']}; "
                f"{device['dpi']}; {device['resolution']}; "
                f"{device['manufacturer']}; {device['device']}; "
                f"{device['model']}; {device['cpu']}; en_US)"
            )
            cl.set_user_agent(user_agent)

            # Get and set proxy
            proxy_used = proxy_manager.get_proxy()
            if proxy_used:
                try:
                    cl.set_proxy(proxy_used)
                    logger.info(f"Attempt {attempt + 1}: Using proxy {proxy_used}")
                except Exception as e:
                    logger.error(f"Proxy setup failed: {e}")
                    proxy_manager.mark_failed(proxy_used)
                    continue
            else:
                logger.warning(f"Attempt {attempt + 1}: No proxy available, using direct connection")

            logger.info(f"Attempt {attempt + 1}: Logging in user: {username}")
            
            if verification_code:
                cl.login(username, password, verification_code=verification_code)
            else:
                cl.login(username, password)

            user_id = cl.user_id
            user_info = cl.user_info(user_id)

            result["success"] = True
            result["message"] = "Login successful"
            result["user_info"] = {
                "user_id": str(user_id),
                "username": user_info.username,
                "full_name": user_info.full_name if user_info.full_name else "",
                "is_verified": user_info.is_verified,
                "is_private": user_info.is_private,
                "follower_count": user_info.follower_count,
                "following_count": user_info.following_count
            }
            
            logger.info(f"Login successful for user: {username}")
            break  # Success, exit retry loop

        except BadPassword:
            logger.warning(f"Bad password for user: {username}")
            result["message"] = "Incorrect password"
            break  # Don't retry on bad password

        except UserNotFound:
            logger.warning(f"User not found: {username}")
            result["message"] = "Username does not exist"
            break  # Don't retry on user not found

        except TwoFactorRequired:
            logger.info(f"2FA required for user: {username}")
            result["requires_2fa"] = True
            result["message"] = "Two-factor authentication required"
            break  # Don't retry on 2FA

        except ChallengeRequired:
            logger.warning(f"Challenge required for user: {username}")
            result["message"] = "Instagram security challenge required. Try a different proxy or wait."
            # Mark proxy as potentially blocked
            if proxy_used:
                proxy_manager.mark_failed(proxy_used)
            # Retry with different proxy
            if attempt < max_retries - 1:
                time.sleep(2)
                continue
            break

        except (PleaseWaitFewMinutes, RateLimitError):
            logger.warning(f"Rate limit for user: {username}")
            result["message"] = "Rate limit hit. Try again in a few minutes."
            # Mark proxy as rate limited
            if proxy_used:
                proxy_manager.mark_failed(proxy_used)
            # Retry with different proxy
            if attempt < max_retries - 1:
                time.sleep(3)
                continue
            break

        except LoginRequired:
            logger.error(f"Login failed for user: {username}")
            result["message"] = "Login failed. Possible IP block. Trying different proxy..."
            # Mark proxy as blocked
            if proxy_used:
                proxy_manager.mark_failed(proxy_used)
            # Retry with different proxy
            if attempt < max_retries - 1:
                time.sleep(2)
                continue
            break

        except Exception as e:
            error_msg = str(e).lower()
            logger.error(f"Error for user {username}: {e}")
            
            # Check if it's a proxy/connection error
            if any(keyword in error_msg for keyword in ['proxy', 'connection', 'timeout', 'network']):
                result["message"] = f"Connection error: {str(e)}"
                if proxy_used:
                    proxy_manager.mark_failed(proxy_used)
                # Retry with different proxy
                if attempt < max_retries - 1:
                    time.sleep(2)
                    continue
            else:
                result["message"] = f"Error: {str(e)}"
            break

    finally:
        if cl:
            try:
                cl.logout()
            except:
                pass

    return result

@app.route('/', methods=['GET'])
@app.route('/api/verify', methods=['GET'])
def index():
    """Health check endpoint"""
    proxy_count = len(proxy_manager.proxies)
    failed_count = len(proxy_manager.failed_proxies)
    
    return jsonify({
        "status": "online",
        "service": "Instagram Verifier API",
        "version": "2.0.0",
        "instagrapi_available": INSTAGRAPI_AVAILABLE,
        "proxy_system": {
            "total_proxies": proxy_count,
            "failed_proxies": failed_count,
            "working_proxies": proxy_count - failed_count
        },
        "endpoints": {
            "verify": "/api/verify (POST)",
            "refresh_proxies": "/api/refresh-proxies (POST)"
        }
    }), 200

@app.route('/api/refresh-proxies', methods=['POST'])
def refresh_proxies():
    """Manually refresh proxy list"""
    try:
        proxy_manager.last_fetch = 0
        proxy_manager.failed_proxies.clear()
        proxy_manager._load_proxies()
        
        return jsonify({
            "success": True,
            "message": "Proxies refreshed",
            "proxy_count": len(proxy_manager.proxies)
        }), 200
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route('/api/verify', methods=['POST', 'OPTIONS'])
def verify_post():
    """Main verification endpoint"""
    
    if request.method == 'OPTIONS':
        response = jsonify({"status": "ok"})
        return response, 200

    try:
        data = request.get_json(force=True)

        if not data:
            return jsonify({
                "success": False,
                "error": "Invalid request: JSON body required"
            }), 400

        username = data.get('username', '').strip()
        password = data.get('password', '')
        verification_code = data.get('verification_code', '').strip()

        if not username or not password:
            return jsonify({
                "success": False,
                "error": "Username and password are required"
            }), 400

        if len(username) < 3:
            return jsonify({
                "success": False,
                "error": "Username must be at least 3 characters"
            }), 400

        result = check_instagram_login(
            username, 
            password, 
            verification_code if verification_code else None
        )

        status_code = 200 if result['success'] else 401
        return jsonify(result), status_code

    except Exception as e:
        logger.error(f"Server error: {str(e)}")
        return jsonify({
            "success": False,
            "error": f"Server error: {str(e)}",
            "message": "An unexpected error occurred"
        }), 500

@app.errorhandler(404)
def not_found(e):
    return jsonify({
        "error": "Endpoint not found",
        "message": "Use POST /api/verify to check credentials"
    }), 404

@app.errorhandler(500)
def internal_error(e):
    logger.error(f"Internal error: {str(e)}")
    return jsonify({
        "error": "Internal server error",
        "message": str(e)
    }), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
