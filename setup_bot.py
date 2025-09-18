#!/usr/bin/env python3
"""
Setup script for Munich Appointment Bot

This script installs required dependencies and sets up the bot environment.
"""

import subprocess
import sys
import os

def install_requirements():
    """Install required Python packages"""
    print("Installing Python dependencies...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
        print("✅ Python dependencies installed successfully")
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to install Python dependencies: {e}")
        return False
    
    return True

def install_playwright():
    """Install Playwright browsers"""
    print("Installing Playwright browsers...")
    try:
        subprocess.check_call([sys.executable, "-m", "playwright", "install", "chromium"])
        print("✅ Playwright browsers installed successfully")
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to install Playwright browsers: {e}")
        return False
    
    return True

def create_env_template():
    """Create environment template file"""
    env_template = """# Munich Appointment Bot Environment Variables
# Copy this file to .env and fill in your values

# Telegram Bot Token (get from @BotFather)
TELEGRAM_BOT_TOKEN=8302207568:AAHihP2Ak_TXpMR8HLrhubGUwZYtw1AUZ2s

# Optional: Custom settings
BOT_LOG_LEVEL=INFO
"""
    
    if not os.path.exists(".env.template"):
        with open(".env.template", "w") as f:
            f.write(env_template)
        print("✅ Created .env.template file")
    else:
        print("ℹ️  .env.template already exists")

def main():
    print("🤖 Munich Appointment Bot Setup")
    print("=" * 35)
    
    success = True
    
    # Install Python requirements
    if not install_requirements():
        success = False
    
    # Install Playwright browsers
    if not install_playwright():
        success = False
    
    # Create environment template
    create_env_template()
    
    if success:
        print("\n✅ Setup completed successfully!")
        print("\nNext steps:")
        print("1. Copy .env.template to .env")
        print("2. Add your Telegram bot token to .env")
        print("3. Run the bot: python appointment_bot.py")
    else:
        print("\n❌ Setup failed. Please check the errors above.")
        sys.exit(1)

if __name__ == "__main__":
    main()