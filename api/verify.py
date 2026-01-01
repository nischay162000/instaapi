from flask import Flask, request, jsonify
from instagrapi import Client
from instagrapi.exceptions import (
    BadPassword, 
    UserNotFound, 
    TwoFactorRequired,
    ChallengeRequired, 
    PleaseWaitFewMinutes,
    RateLimitError
)
import random
import os

app = Flask(__name__)

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

@app.route('/', methods=['POST', 'OPTIONS'])
@app.route('/api/verify', methods=['POST', 'OPTIONS'])
def verify():
    # Handle CORS preflight
    if request.method == 'OPTIONS':
        response = jsonify({'status': 'ok'})
        response.headers.add('Access-Control-Allow-Origin', '*')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type')
        response.headers.add('Access-Control-Allow-Methods', 'POST, OPTIONS')
        return response, 200
    
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({"error": "No data provided"}), 400
        
        username = data.get('username', '').strip()
        password = data.get('password', '')
        verification_code = data.get('verification_code', '').strip()
        
        if not username or not password:
            return jsonify({
                "success": False,
                "error": "Username and password are required"
            }), 400
        
        result = check_instagram_login(username, password, verification_code)
        
        response = jsonify(result)
        response.headers.add('Access-Control-Allow-Origin', '*')
        return response, 200 if result.get('success') else 401
        
    except Exception as e:
        response = jsonify({"success": False, "error": f"Server error: {str(e)}"})
        response.headers.add('Access-Control-Allow-Origin', '*')
        return response, 500

def check_instagram_login(username, password, verification_code=None):
    """Check Instagram credentials with all error handling"""
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
        cl.set_user_agent(
            f"Instagram {device['app_version']} Android "
            f"({device['android_version']}/{device['android_release']}; "
            f"{device['dpi']}; {device['resolution']}; "
            f"{device['manufacturer']}; {device['device']}; "
            f"{device['model']}; {device['cpu']}; en_US)"
        )
        
        # Set proxy if available in environment
        proxy = os.getenv('INSTAGRAM_PROXY')
        if proxy:
            cl.set_proxy(proxy)
        
        # Perform login
        if verification_code:
            cl.login(username, password, verification_code=verification_code)
        else:
            cl.login(username, password)
        
        # Get user information
        user_id = cl.user_id
        user_info = cl.user_info(user_id)
        
        result["success"] = True
        result["message"] = "✅ Login successful!"
        result["user_info"] = {
            "user_id": str(user_id),
            "username": user_info.username,
            "full_name": user_info.full_name,
            "is_verified": user_info.is_verified,
            "is_private": user_info.is_private,
            "follower_count": user_info.follower_count,
            "following_count": user_info.following_count,
            "media_count": user_info.media_count
        }
        
    except BadPassword:
        result["message"] = "❌ Incorrect password. Please try again."
        
    except UserNotFound:
        result["message"] = "❌ Username does not exist on Instagram."
        
    except TwoFactorRequired:
        result["requires_2fa"] = True
        result["message"] = "🔐 Two-factor authentication required. Please enter your verification code."
        
    except ChallengeRequired:
        result["message"] = "⚠️ Instagram security challenge required. Please verify your account through the Instagram app first."
        
    except PleaseWaitFewMinutes:
        result["message"] = "⏳ Too many login attempts. Please wait 5-10 minutes and try again."
        
    except RateLimitError:
        result["message"] = "🚫 Rate limit exceeded. Please try again later."
        
    except Exception as e:
        result["message"] = f"❌ Error: {str(e)}"
    
    return result

# For local testing
if __name__ == '__main__':
    app.run(debug=True, port=5000)
