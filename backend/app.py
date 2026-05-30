from flask import Flask, request, send_file, render_template_string
from flask_cors import CORS
import requests
import io
import random
import time
import os

app = Flask(__name__)
CORS(app)

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
    </style>
</head>
<body>
    <div class="card">
        <h2>🖼️ AI Image Generator</h2>
        <p style="color:#64748b;">Powered by Pollinations.ai &bull; <span style="background:#e2e8f0;padding:0.25rem 0.75rem;border-radius:999px;font-size:0.75rem;font-weight:600;">Free</span></p>

        <textarea id="prompt" rows="3" placeholder="Describe your image...">Astronaut riding a horse, realistic, 4k</textarea>
        <button id="generateBtn">🔄 Generate Image</button>
        <div id="status">Ready</div>
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
                    const errText = await resp.text();
                    throw new Error(errText);
                }
                
                const blob = await resp.blob();
                const url = URL.createObjectURL(blob);
                
                document.getElementById('generatedImage').src = url;
                document.getElementById('generatedImage').style.display = 'block';
                document.getElementById('downloadBtn').href = url;
                document.getElementById('downloadBtn').download = `tti-${Date.now()}.png`;
                document.getElementById('downloadBtn').classList.add('visible');
                document.getElementById('status').textContent = '✅ Done!';
            } catch (err) {
                document.getElementById('status').textContent = '❌ ' + err.message;
            } finally {
                document.getElementById('generateBtn').disabled = false;
            }
        });
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_PAGE)

@app.route('/generate', methods=['POST'])
def generate():
    data = request.json
    prompt = data.get('prompt', 'a beautiful landscape')

    # ✅ Pollinations.ai with random seed to avoid caching
    seed = random.randint(1, 999999)
    url = f"https://image.pollinations.ai/prompt/{prompt}?seed={seed}"

    try:
        response = requests.get(url, timeout=90)
        if response.status_code != 200:
            return {"error": "Pollinations.ai error"}, 500
        return send_file(
            io.BytesIO(response.content),
            mimetype='image/png',
            as_attachment=True,
            download_name='image.png'
        )
    except Exception as e:
        return {"error": str(e)}, 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
