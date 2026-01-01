from http.server import BaseHTTPRequestHandler
import json
import os
from instagrapi import Client
from instagrapi.exceptions import (
    BadPassword, UserNotFound, TwoFactorRequired,
    ChallengeRequired, PleaseWaitFewMinutes
)
import random

class handler(BaseHTTPRequestHandler):
    
    def get_android_device(self):
        """Generate realistic Android device"""
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
    
    def check_login(self, username, password, verification_code=None):
        """Check Instagram credentials"""
        result = {
            "success": False,
            "message": "",
            "user_info": None,
            "requires_2fa": False
        }
        
        try:
            cl = Client()
            
            # Set mobile device
            device = self.get_android_device()
            cl.set_device(device)
            
            # Set realistic user agent
            cl.set_user_agent(
                f"Instagram {device['app_version']} Android "
                f"({device['android_version']}/{device['android_release']}; "
                f"{device['dpi']}; {device['resolution']}; "
                f"{device['manufacturer']}; {device['device']}; "
                f"{device['model']}; {device['cpu']}; en_US)"
            )
            
            # Set proxy from environment variable if available
            proxy = os.getenv('PROXY_URL')
            if proxy:
                cl.set_proxy(proxy)
            
            # Perform login
            if verification_code:
                cl.login(username, password, verification_code=verification_code)
            else:
                cl.login(username, password)
            
            # Get user info
            user_id = cl.user_id
            user_info = cl.user_info(user_id)
            
            result["success"] = True
            result["message"] = "Login successful"
            result["user_info"] = {
                "user_id": str(user_id),
                "username": user_info.username,
                "full_name": user_info.full_name,
                "is_verified": user_info.is_verified,
                "is_private": user_info.is_private,
                "follower_count": user_info.follower_count
            }
            
        except BadPassword:
            result["message"] = "Incorrect password"
        except UserNotFound:
            result["message"] = "Username does not exist"
        except TwoFactorRequired:
            result["requires_2fa"] = True
            result["message"] = "Two-factor authentication required"
        except ChallengeRequired:
            result["message"] = "Instagram security challenge required"
        except PleaseWaitFewMinutes:
            result["message"] = "Too many attempts. Please wait"
        except Exception as e:
            result["message"] = f"Error: {str(e)}"
        
        return result
    
    def do_POST(self):
        """Handle POST requests"""
        try:
            # Read request body
            content_length = int(self.headers['Content-Length'])
            body = self.rfile.read(content_length)
            data = json.loads(body.decode('utf-8'))
            
            username = data.get('username')
            password = data.get('password')
            verification_code = data.get('verification_code')
            
            if not username or not password:
                self.send_response(400)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps({
                    "error": "Username and password required"
                }).encode())
                return
            
            # Check login
            result = self.check_login(username, password, verification_code)
            
            # Send response
            self.send_response(200 if result['success'] else 401)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps(result).encode())
            
        except Exception as e:
            self.send_response(500)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps({
                "error": str(e)
            }).encode())
    
    def do_OPTIONS(self):
        """Handle CORS preflight"""
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
