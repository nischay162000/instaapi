from flask import Flask, request, jsonify
from flask_cors import CORS
import sys
import os

# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(__file__))

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

# Simple in-memory storage for testing
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

import random
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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
        }
    ]
    return random.choice(devices)

def check_instagram_login(username, password, verification_code=None):
    """Check Instagram login credentials"""
    
    if not INSTAGRAPI_AVAILABLE:
        return {
            "success": False,
            "message": "Instagram API library not available. Please check server configuration.",
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

        proxy_url = os.getenv('PROXY_URL')
        if proxy_url:
            cl.set_proxy(proxy_url)

        logger.info(f"Attempting login for user: {username}")
        
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

    except BadPassword:
        logger.warning(f"Bad password for user: {username}")
        result["message"] = "Incorrect password"

    except UserNotFound:
        logger.warning(f"User not found: {username}")
        result["message"] = "Username does not exist"

    except TwoFactorRequired:
        logger.info(f"2FA required for user: {username}")
        result["requires_2fa"] = True
        result["message"] = "Two-factor authentication required"

    except ChallengeRequired:
        logger.warning(f"Challenge required for user: {username}")
        result["message"] = "Instagram security challenge required"

    except PleaseWaitFewMinutes:
        logger.warning(f"Rate limit for user: {username}")
        result["message"] = "Too many attempts. Please wait 5-10 minutes"

    except RateLimitError:
        logger.warning(f"Rate limit error for user: {username}")
        result["message"] = "Rate limit exceeded. Try again later"

    except LoginRequired:
        logger.error(f"Login failed for user: {username}")
        result["message"] = "Login failed. Please try again"

    except Exception as e:
        logger.error(f"Error for user {username}: {str(e)}")
        result["message"] = f"Login error: {str(e)}"

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
    return jsonify({
        "status": "online",
        "service": "Instagram Verifier API",
        "version": "1.0.0",
        "instagrapi_available": INSTAGRAPI_AVAILABLE,
        "endpoints": {
            "verify": "/api/verify (POST)"
        }
    }), 200

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

# Vercel expects the app object to be named 'app'
# This is the entry point for Vercel serverless functions
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
