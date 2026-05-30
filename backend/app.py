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
# HTML PAGE with credit-aware frontend
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
        button:disabled { background: #94a3b8; cursor: not-allowed; }
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
        <div class="controls-row" style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-top:12px;">
            <div><label for="size">Size</label><select id="size"><option value="1024x1024">1024×1024</option><option value="1024x768">1024×768</option><option value="768x1024">768×1024</option></select></div>
            <div><label for="steps">Steps</label><input type="number" id="steps" value="25" min="10" max="50" /></div>
        </div>
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
        const generateBtn = document.getElementById('generateBtn');
        const statusDiv = document.getElementById('status');
        const creditDisplay = document.getElementById('creditDisplay');
        const generatedImage = document.getElementById('generatedImage');
        const downloadBtn = document.getElementById('downloadBtn');
        const promptInput = document.getElementById('prompt');
        const sizeSelect = document.getElementById('size');
        const stepsInput = document.getElementById('steps');

        async function loadCredits() {
            try {
                const resp = await fetch('/credits');
                const data = await resp.json();
                creditDisplay.textContent = data.message;
                // 🔒 Disable button if credits are exhausted
                if (!data.allowed) {
                    generateBtn.disabled = true;
                    generateBtn.style.background = '#94a3b8';
                    generateBtn.textContent = '⛔ No credits left';
                }
            } catch (err) {
                creditDisplay.textContent = 'Could not load credits';
            }
        }
        loadCredits();

        generateBtn.addEventListener('click', async function() {
            const prompt = promptInput.value.trim();
            if (!prompt) { statusDiv.textContent = '⚠️ Please enter a prompt.'; return; }

            generateBtn.disabled = true;
            statusDiv.textContent = '⏳ Generating...';
            generatedImage.style.display = 'none';
            downloadBtn.classList.remove('visible');

            try {
                const resp = await fetch('/generate', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        prompt: prompt,
                        size: sizeSelect.value,
                        steps: parseInt(stepsInput.value)
                    })
                });

                if (!resp.ok) {
                    const errorData = await resp.json();
                    const msg = errorData.message || 'Server error';
                    statusDiv.textContent = '❌ ' + msg;
                    creditDisplay.textContent = msg;
                    if (msg.includes('Daily limit')) {
                        generateBtn.disabled = true;
                        generateBtn.textContent = '⛔ No credits left';
                    }
                    return;
                }

                const blob = await resp.blob();
                const url = URL.createObjectURL(blob);
                generatedImage.src = url;
                generatedImage.style.display = 'block';
                downloadBtn.href = url;
                downloadBtn.download = `tti-${Date.now()}.png`;
                downloadBtn.classList.add('visible');
                statusDiv.textContent = '✅ Image generated!';

                const creditResp = await fetch('/credits');
                const creditData = await creditResp.json();
                creditDisplay.textContent = creditData.message;
                if (!creditData.allowed) {
                    generateBtn.disabled = true;
                    generateBtn.textContent = '⛔ No credits left';
                }
            } catch (err) {
                statusDiv.textContent = '❌ ' + err.message;
            } finally {
                if (!generateBtn.disabled) generateBtn.disabled = false;
            }
        });
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
    steps = data.get('steps', 25)
    ip = get_client_ip()  # ✅ Added

    allowed, remaining, message = check_credits(ip)
    if not allowed:
        return jsonify({"error": "credit_limit", "message": message}), 429

    seed = random.randint(1, 999999)
    # ✅ Use size correctly (no overwriting)
    url = f"https://image.pollinations.ai/prompt/{prompt}?seed={seed}&width={size.split('x')[0]}&height={size.split('x')[1]}"

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