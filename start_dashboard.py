#!/usr/bin/env python3
"""
Dashboard Launcher for Stock Market Analytics
Run this script to start the real-time analytics dashboard
"""

import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add the project root to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def main():
    """Start the dashboard"""
    try:
        from dashboard.app import app
        
        print("🚀 Starting Stock Market Analytics Dashboard...")
        print("📊 Dashboard will be available at: http://localhost:8050")
        print("🔄 Auto-refresh every 10 seconds")
        print("⏹️  Press Ctrl+C to stop the dashboard")
        print("-" * 50)
        
        # Start the dashboard
        app.run(
            debug=True,
            host='0.0.0.0',
            port=8050,
            dev_tools_hot_reload=True
        )
        
    except ImportError as e:
        print(f"❌ Error importing dashboard: {e}")
        print("💡 Make sure you have installed all requirements:")
        print("   pip install -r requirements.txt")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error starting dashboard: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 