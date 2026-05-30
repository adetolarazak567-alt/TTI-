from flask import Flask, request, send_file, render_template_string, jsonify
from flask_cors import CORS
import requests
import io
import random
import time
import os
from collections import defaultdict
from datetime import datetime, timedelta

app = Flask(__name__)
CORS(app)

# ============================================================
# 🔒 SECURE CREDIT SYSTEM (15 images per day per IP)
# ============================================================
# This stores data in memory (resets if Render restarts, but that's acceptable)
credit_store = defaultdict(lambda: {"count": 0, "reset_time": datetime.now() + timedelta(days=1)})

def get_client_ip():
    """Get real client IP address behind Render proxy"""
    if request.headers.get('X-Forwarded-For'):
        return request.headers.get('X-Forwarded-For').split(',')[0].strip()
    return request.remote_addr

def check_credits(ip):
    """Check if IP has credits left. Returns (allowed, remaining, message)"""
    now = datetime.now()
    record = credit_store[ip]
    
    # Reset if 24 hours have passed
    if now > record["reset_time"]:
        record["count"] = 0
        record["reset_time"] = now + timedelta(days=1)
    
    remaining = 15 - record["count"]
    
    if remaining <= 0:
        # Calculate time until reset
        time_left = record["reset_time"] - now
        hours = int(time_left.total_seconds() // 3600)
        minutes = int((time_left.total_seconds() % 3600) // 60)
        return False, 0, f"Daily limit reached. You've used all 15 credits. Please wait {hours}h {minutes}m for reset."
    
    return True, remaining, f"{remaining} credits remaining today."

def use_credit(ip):
    """Consume one credit for the given IP"""
    record = credit_store[ip]
    record["count"] += 1
    return record["count"]

# ============================================================
# HTML PAGE (Unchanged UI)
# ============================================================
HTML_PAGE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>TTI – AI Image Generator</title>
    <style>
        body { font-family: sans-serif; max-width: 600px; margin: 2rem auto; padding: 1rem; background: #f5f7fa; }
        .card { background: white; padding: 2rem; border-radius: 20px; box-shadow: 0 8px 30px rgba(0,0,0,0.05); }
        textarea { width: 100%; height: 80px; padding: 0.5rem; border: 2px solid #e2e8f0; border-radius: 8px; font-size: 1rem; }
        button { width: 100%; padding: 0.75rem; background: #4f46e5; color: white; border: none; border-radius: 8px; font-weight: bold; cursor: pointer; margin-top: 1rem; }
        #status { margin-top: 1rem; font-weight: 500; color: #475569; }
        img { max-width: 100%; border-radius: 12px; margin-top: 12px; display: none; }
        .download-btn { display: none; margin-top: 8px; padding: 0.5rem 1rem; background: #16a34a; color: white; border-radius: 8px; text-decoration: none; cursor: pointer; }
        .download-btn.visible { display: inline-block; }
        #creditDisplay { margin-top: 10px; font-size: 0.9rem; color: #64748b; text-align: center; }
    </style>
</head>
<body>
    <div class="card">
        <h2>🖼️ AI Image Generator</h2>
        <p style="color:#64748b;">Free tier: <strong>15 images per day</strong> &bull; <span style="background:#e2e8f0;padding:0.25rem 0.75rem;border-radius:999px;font-size:0.75rem;font-weight:600;">Secure credit system</span></p>

        <textarea id="prompt" rows="3" placeholder="Describe your image...">Astronaut riding a horse, realistic, 4k</textarea>
        <button id="generateBtn">🔄 Generate Image</button>
        <div id="status">Ready</div>
        <div id="creditDisplay">Loading credits...</div>
        <div id="result">
            <img id="generatedImage" />
            <br>
            <a id="downloadBtn" class="download-btn">⬇️ Download Image</a>
        </div>
    </div>

    <script>
        document.getElementById('generateBtn').addEventListener('click', async function() {
            const prompt = document.getElementById('prompt').value.trim();
            if (!prompt) {
                document.getElementById('status').textContent = '⚠️ Please enter a prompt.';
                return;
            }

            document.getElementById('generateBtn').disabled = true;
            document.getElementById('status').textContent = '⏳ Generating...';
            document.getElementById('generatedImage').style.display = 'none';
            document.getElementById('downloadBtn').classList.remove('visible');

            try {
                const resp = await fetch('/generate', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ prompt })
                });

                if (!resp.ok) {
                    const errorData = await resp.json();
                    if (errorData.message) {
                        document.getElementById('status').textContent = '❌ ' + errorData.message;
                        document.getElementById('creditDisplay').textContent = errorData.message;
                    } else {
                        document.getElementById('status').textContent = '❌ Server error';
                    }
                    return;
                }
                
                const blob = await resp.blob();
                const url = URL.createObjectURL(blob);
                
                document.getElementById('generatedImage').src = url;
                document.getElementById('generatedImage').style.display = 'block';
                document.getElementById('downloadBtn').href = url;
                document.getElementById('downloadBtn').download = `tti-${Date.now()}.png`;
                document.getElementById('downloadBtn').classList.add('visible');
                document.getElementById('status').textContent = '✅ Image generated!';
                
                // Refresh credit display
                const creditResp = await fetch('/credits');
                const creditData = await creditResp.json();
                document.getElementById('creditDisplay').textContent = creditData.message;
            } catch (err) {
                document.getElementById('status').textContent = '❌ ' + err.message;
            } finally {
                document.getElementById('generateBtn').disabled = false;
            }
        });

        // Load credits on page load
        async function loadCredits() {
            try {
                const creditResp = await fetch('/credits');
                const creditData = await creditResp.json();
                document.getElementById('creditDisplay').textContent = creditData.message;
            } catch (err) {
                document.getElementById('creditDisplay').textContent = 'Could not load credits';
            }
        }
        loadCredits();
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_PAGE)

@app.route('/credits')
def get_credits():
    ip = get_client_ip()
    allowed, remaining, message = check_credits(ip)
    return jsonify({"allowed": allowed, "remaining": remaining, "message": message})

@app.route('/generate', methods=['POST'])
def generate():
    data = request.json
    prompt = data.get('prompt', 'a beautiful landscape')
    size = data.get('size', '1024x1024')
    seed = random.randint(1, 999999)
    url = f"https://image.pollinations.ai/prompt/{prompt}?seed={seed}&width={size.split('x')[0]}&height={size.split('x')[1]}"

    # ============================================================
    # 🔒 Check credit limit
    # ============================================================
    allowed, remaining, message = check_credits(ip)
    if not allowed:
        return jsonify({"error": "credit_limit", "message": message}), 429

    # ============================================================
    # Generate image (Pollinations.ai)
    # ============================================================
    seed = random.randint(1, 999999)
    url = f"https://image.pollinations.ai/prompt/{prompt}?seed={seed}"

    try:
        response = requests.get(url, timeout=90)
        if response.status_code != 200:
            return jsonify({"error": "api_error", "message": "Image generation service error"}), 500

        # ✅ Use one credit
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