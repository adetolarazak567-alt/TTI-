from flask import Flask, request, send_file, render_template_string, jsonify
from flask_cors import CORS
import requests
import io
import random
import os

app = Flask(__name__)
CORS(app)

# ============================================================
# CREDIT SYSTEM (15 images per day per IP)
# ============================================================
from collections import defaultdict
from datetime import datetime, timedelta

credit_store = defaultdict(lambda: {"count": 0, "reset_time": datetime.now() + timedelta(days=1)})

def get_client_ip():
    if request.headers.get('X-Forwarded-For'):
        return request.headers.get('X-Forwarded-For').split(',')[0].strip()
    return request.remote_addr

def check_credits(ip):
    now = datetime.now()
    record = credit_store[ip]
    if now > record["reset_time"]:
        record["count"] = 0
        record["reset_time"] = now + timedelta(days=1)
    remaining = 15 - record["count"]
    if remaining <= 0:
        time_left = record["reset_time"] - now
        hours = int(time_left.total_seconds() // 3600)
        minutes = int((time_left.total_seconds() % 3600) // 60)
        return False, 0, f"Daily limit reached. You've used all 15 credits. Please wait {hours}h {minutes}m for reset."
    return True, remaining, f"{remaining} credits remaining today."

def use_credit(ip):
    credit_store[ip]["count"] += 1

# ============================================================
# ROUTES
# ============================================================
@app.route('/')
def index():
    return "TTI Backend is running."

@app.route('/credits')
def get_credits():
    ip = get_client_ip()
    allowed, remaining, message = check_credits(ip)
    return jsonify({"allowed": allowed, "remaining": remaining, "message": message})

@app.route('/generate', methods=['POST'])
def generate():
    data = request.json
    prompt = data.get('prompt', 'a beautiful landscape')
    # Ignore extra fields to avoid confusion
    ip = get_client_ip()

    allowed, remaining, message = check_credits(ip)
    if not allowed:
        return jsonify({"error": "credit_limit", "message": message}), 429

    # ✅ Generate unique image every time
    seed = random.randint(1, 999999)
    url = f"https://image.pollinations.ai/prompt/{prompt}?seed={seed}&width=1024&height=1024"

    try:
        response = requests.get(url, timeout=90)
        if response.status_code != 200:
            return jsonify({"error": "api_error", "message": "Image generation service error"}), 500
        
        use_credit(ip)
        return send_file(
            io.BytesIO(response.content),
            mimetype='image/png',
            as_attachment=True,
            download_name='image.png'
        )
    except Exception as e:
        return jsonify({"error": "exception", "message": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)