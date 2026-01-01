from flask import Flask, request, jsonify
from flask_cors import CORS
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
import random
import os
import sys

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

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
        },
        {
            "app_version": "267.0.0.18.75",
            "android_version": 32,
            "android_release": "12.0",
            "dpi": "440dpi",
            "resolution": "1080x2400",
            "manufacturer": "Realme",
            "device": "RMX3461",
            "model": "Realme GT Neo 3",
            "cpu": "mt6895"
        }
    ]
    return random.choice(devices)

def check_instagram_login(username, password, verification_code=None):
    """
    Check Instagram login credentials
    Returns dict with status and user info
    """
    result = {
        "success": False,
        "message": "",
        "user_info": None,
        "requires_2fa": False
    }

    try:
        # Initialize Instagram client
        cl = Client()

        # Set realistic mobile device
        device = get_android_device()
        cl.set_device(device)

        # Set realistic user agent
        user_agent = (
            f"Instagram {device['app_version']} Android "
            f"({device['android_version']}/{device['android_release']}; "
            f"{device['dpi']}; {device['resolution']}; "
            f"{device['manufacturer']}; {device['device']}; "
            f"{device['model']}; {device['cpu']}; en_US)"
        )
        cl.set_user_agent(user_agent)

        # Set proxy if available from environment
        proxy_url = os.getenv('PROXY_URL')
        if proxy_url:
            cl.set_proxy(proxy_url)

        # Perform login
        if verification_code:
            cl.login(username, password, verification_code=verification_code)
        else:
            cl.login(username, password)

        # Get user information
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

    except BadPassword as e:
        result["message"] = "Incorrect password"

    except UserNotFound as e:
        result["message"] = "Username does not exist"

    except TwoFactorRequired as e:
        result["requires_2fa"] = True
        result["message"] = "Two-factor authentication required"

    except ChallengeRequired as e:
        result["message"] = "Instagram security challenge required. Verify via Instagram app"

    except PleaseWaitFewMinutes as e:
        result["message"] = "Too many attempts. Please wait 5-10 minutes"

    except RateLimitError as e:
        result["message"] = "Rate limit exceeded. Try again later"

    except LoginRequired as e:
        result["message"] = "Login failed. Please try again"

    except Exception as e:
        result["message"] = f"Error: {str(e)}"

    return result

@app.route('/', methods=['GET'])
@app.route('/api/verify', methods=['GET'])
def index():
    """Root endpoint - health check"""
    return jsonify({
        "status": "online",
        "service": "Instagram Verifier API",
        "version": "1.0.0",
        "endpoints": {
            "verify": "/api/verify (POST)"
        }
    }), 200

@app.route('/', methods=['POST', 'OPTIONS'])
@app.route('/api/verify', methods=['POST', 'OPTIONS'])
def verify():
    """Main verification endpoint"""

    # Handle CORS preflight
    if request.method == 'OPTIONS':
        response = jsonify({"status": "ok"})
        response.headers.add('Access-Control-Allow-Origin', '*')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type')
        response.headers.add('Access-Control-Allow-Methods', 'POST, OPTIONS')
        return response, 200

    try:
        # Get JSON data from request
        data = request.get_json(force=True)

        if not data:
            return jsonify({
                "success": False,
                "error": "Invalid request: JSON body required"
            }), 400

        username = data.get('username', '').strip()
        password = data.get('password', '')
        verification_code = data.get('verification_code', '').strip()

        # Validate inputs
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

        # Check login
        result = check_instagram_login(
            username, 
            password, 
            verification_code if verification_code else None
        )

        # Return response with proper status code
        status_code = 200 if result['success'] else 401
        response = jsonify(result)
        response.headers.add('Access-Control-Allow-Origin', '*')

        return response, status_code

    except Exception as e:
        # Catch any unexpected errors
        error_response = jsonify({
            "success": False,
            "error": f"Server error: {str(e)}",
            "message": "An unexpected error occurred"
        })
        error_response.headers.add('Access-Control-Allow-Origin', '*')
        return error_response, 500

@app.errorhandler(404)
def not_found(e):
    """Handle 404 errors"""
    return jsonify({
        "error": "Endpoint not found",
        "message": "Use POST /api/verify to check credentials"
    }), 404

@app.errorhandler(500)
def internal_error(e):
    """Handle 500 errors"""
    return jsonify({
        "error": "Internal server error",
        "message": str(e)
    }), 500

# For local testing
if __name__ == '__main__':
    print("Starting Instagram Verifier API...")
    print("Running on http://localhost:5000")
    app.run(host='0.0.0.0', port=5000, debug=True)
