from flask import Flask, jsonify
import threading
import time
import os

app = Flask(__name__)

# Bot start time for uptime calculation
start_time = time.time()

@app.route('/')
def home():
    """Main endpoint that hosting services will ping"""
    uptime_seconds = int(time.time() - start_time)
    hours = uptime_seconds // 3600
    minutes = (uptime_seconds % 3600) // 60
    seconds = uptime_seconds % 60
    
    return jsonify({
        "status": "alive",
        "message": "Telegram Bot is running!",
        "uptime": f"{hours:02d}:{minutes:02d}:{seconds:02d}",
        "timestamp": int(time.time())
    })

@app.route('/health')
def health():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "service": "telegram-autograb-bot",
        "timestamp": int(time.time())
    })

@app.route('/ping')
def ping():
    """Simple ping endpoint"""
    return "pong"

@app.route('/status')
def status():
    """Detailed status endpoint"""
    uptime_seconds = int(time.time() - start_time)
    return jsonify({
        "bot_status": "running",
        "uptime_seconds": uptime_seconds,
        "uptime_formatted": f"{uptime_seconds // 3600:02d}:{(uptime_seconds % 3600) // 60:02d}:{uptime_seconds % 60:02d}",
        "server_time": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
        "environment": {
            "python_version": os.sys.version,
            "platform": os.name
        }
    })

def run_flask():
    """Run Flask server"""
    # Get port from environment variable (for Railway, Render, etc.)
    port = int(os.environ.get("PORT", 8000))
    
    # Run Flask server
    app.run(
        host="0.0.0.0",  # Listen on all interfaces
        port=port,
        debug=False,     # Disable debug mode in production
        use_reloader=False  # Disable auto-reload to prevent conflicts
    )

def keep_alive():
    """Start the Flask server in a separate daemon thread"""
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    
    print(f"🌐 Flask keep-alive server started on port {os.environ.get('PORT', 8000)}")
    print("🔗 Available endpoints:")
    print("   / - Main status")
    print("   /health - Health check") 
    print("   /ping - Simple ping")
    print("   /status - Detailed status")

if __name__ == "__main__":
    # If running keep_alive.py directly
    print("Starting Flask keep-alive server...")
    run_flask()
