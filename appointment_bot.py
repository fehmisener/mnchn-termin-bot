import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional

from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
import httpx
from playwright.async_api import async_playwright, Browser, Page

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Reduce noise from external libraries
logging.getLogger('httpx').setLevel(logging.WARNING)
logging.getLogger('httpcore').setLevel(logging.WARNING)
logging.getLogger('telegram').setLevel(logging.WARNING)
logging.getLogger('telegram.ext').setLevel(logging.WARNING)
logging.getLogger('urllib3').setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

class ProxyConfig:
    def __init__(self, proxy_user: str, proxy_password: str, proxy_host: str = "x.botproxy.net", proxy_port: int = 8080):
        self.proxy_user = proxy_user
        self.proxy_password = proxy_password
        self.proxy_host = proxy_host
        self.proxy_port = proxy_port
        self.proxy_url = f"http://{proxy_user}:{proxy_password}@{proxy_host}:{proxy_port}"
    
    def get_httpx_proxy_url(self):
        return self.proxy_url
    
    def get_playwright_proxy(self):
        return {
            "server": f"http://{self.proxy_host}:{self.proxy_port}",
            "username": self.proxy_user,
            "password": self.proxy_password
        }

class MunichAppointmentBot:
    def __init__(self, telegram_token: str, proxy_user: Optional[str] = None, proxy_password: Optional[str] = None):
        self.telegram_token = telegram_token
        self.application = ApplicationBuilder().token(telegram_token).build()
        self.browser: Optional[Browser] = None
        self.page: Optional[Page] = None
        self.current_token: Optional[str] = None
        self.token_expires_at: Optional[datetime] = None
        self.is_monitoring = False
        self.monitoring_interval = 5  # Default 5 minutes
        self.chat_id: Optional[int] = None
        
        # Proxy configuration
        self.proxy_config = None
        if proxy_user and proxy_password:
            self.proxy_config = ProxyConfig(proxy_user, proxy_password)
        
        # Munich appointment system URLs and IDs
        self.base_url = "https://www48.muenchen.de/buergeransicht/api/citizen"
        self.office_id = "10187259"
        self.service_id = "10339027"
        
        # Headers for API requests
        self.headers = {
            'Accept': '*/*',
            'Accept-Language': 'en-GB,en;q=0.9,en-US;q=0.8,tr;q=0.7',
            'Connection': 'keep-alive',
            'Origin': 'https://stadt.muenchen.de',
            'Referer': 'https://stadt.muenchen.de/',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-site',
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36 Edg/140.0.0.0',
            'sec-ch-ua': '"Chromium";v="140", "Not=A?Brand";v="24", "Microsoft Edge";v="140"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"macOS"'
        }
        
        self._setup_handlers()
    
    def _setup_handlers(self):
        """Setup telegram bot command handlers"""
        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(CommandHandler("help", self.help_command))
        self.application.add_handler(CommandHandler("health", self.health_command))
        self.application.add_handler(CommandHandler("regular", self.regular_command))
        self.application.add_handler(CommandHandler("single", self.single_command))
        self.application.add_handler(CommandHandler("stop", self.stop_command))
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        self.chat_id = update.effective_chat.id
        await update.message.reply_text(
            "🤖 Munich Appointment Bot Started!\n\n"
            "I'll help you monitor appointment availability for Munich services.\n"
            "Use /help to see available commands."
        )
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command"""
        help_text = """
🤖 Munich Appointment Bot Commands:

/start - Initialize the bot
/help - Show this help message
/health - Check bot status
/single - Check for appointments once
/regular <minutes> - Start regular monitoring (e.g., /regular 5)
/stop - Stop regular monitoring

📍 Monitoring: Munich Bürgerservice appointments
🏢 Office: Location 10187259
🔧 Service: 10339027
        """
        await update.message.reply_text(help_text)
    
    async def health_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /health command"""
        status = "✅ Running" if self.is_monitoring else "⏹️ Stopped"
        token_status = "🟢 Valid" if self._is_token_valid() else "🔴 Expired/None"
        
        health_info = f"""
🏥 Bot Health Status:

Status: {status}
Token: {token_status}
Monitoring Interval: {self.monitoring_interval} minutes
Last Token Refresh: {self.token_expires_at.strftime('%H:%M:%S') if self.token_expires_at else 'Never'}
Browser: {'🟢 Active' if self.browser else '🔴 Inactive'}
        """
        await update.message.reply_text(health_info)
    
    async def regular_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /regular command"""
        try:
            if context.args and len(context.args) > 0:
                minutes = int(context.args[0])
                if minutes < 1:
                    await update.message.reply_text("❌ Interval must be at least 1 minute")
                    return
                
                self.monitoring_interval = minutes
                self.chat_id = update.effective_chat.id
                
                if not self.is_monitoring:
                    self.is_monitoring = True
                    asyncio.create_task(self._start_monitoring())
                
                await update.message.reply_text(
                    f"✅ Regular monitoring started!\n"
                    f"⏱️ Checking every {minutes} minutes"
                )
            else:
                await update.message.reply_text(
                    "❌ Please specify interval in minutes\n"
                    "Example: /regular 5"
                )
        except ValueError:
            await update.message.reply_text("❌ Please provide a valid number of minutes")
    
    async def single_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /single command"""
        self.chat_id = update.effective_chat.id
        await update.message.reply_text("🔍 Checking for appointments...")
        
        try:
            result = await self._check_appointments()
            if result:
                await update.message.reply_text(
                    f"🎉 APPOINTMENT AVAILABLE!\n{result}"
                )
            else:
                await update.message.reply_text("😞 No appointments available")
        except Exception as e:
            logger.error(f"Error during single check: {e}")
            await update.message.reply_text(f"❌ Error checking appointments: {str(e)}")
    
    async def stop_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /stop command"""
        self.is_monitoring = False
        await update.message.reply_text("⏹️ Regular monitoring stopped")
    
    def _is_token_valid(self) -> bool:
        """Check if current token is valid"""
        if not self.current_token or not self.token_expires_at:
            return False
        return datetime.now() < self.token_expires_at
    
    async def _cleanup_browser_state(self):
        """Clean up browser state for fresh token generation"""
        if self.page:
            try:
                await self.page.context.clear_cookies()
                await self.page.context.clear_permissions()
                # Close current page to force fresh state
                await self.page.close()
                self.page = None
                self.token_expires_at = None
                self.current_token = None
            except Exception as e:
                logger.debug(f"Error cleaning browser state: {e}")
    
    async def _start_monitoring(self):
        """Start the monitoring loop"""
        while self.is_monitoring:
            try:
                result = await self._check_appointments()
                if result and self.chat_id:
                    await self.application.bot.send_message(
                        chat_id=self.chat_id,
                        text=f"🎉 APPOINTMENT AVAILABLE!\n{result}"
                    )
                    # Stop monitoring after finding appointment
                    self.is_monitoring = False
                    await self.application.bot.send_message(
                        chat_id=self.chat_id,
                        text="✅ Monitoring stopped - appointment found!"
                    )
                    break
                
                # Wait for the specified interval
                await asyncio.sleep(self.monitoring_interval * 60)
                
            except Exception as e:
                error_message = str(e)
                logger.error(f"Error in monitoring loop: {error_message}")
                
                # Check if this is a recoverable captcha token error
                if "Invalid captcha token" in error_message or "captcha" in error_message.lower():
                    logger.info("Captcha token error detected - browser state cleaned, continuing monitoring...")
                    # Short wait before retrying
                    await asyncio.sleep(30)
                else:
                    # For other errors, notify and wait longer
                    if self.chat_id:
                        await self.application.bot.send_message(
                            chat_id=self.chat_id,
                            text=f"❌ Monitoring error: {error_message}"
                        )
                    await asyncio.sleep(60)  # Wait 1 minute before retrying
    
    async def _init_browser(self):
        """Initialize Playwright browser"""
        if not self.browser:
            playwright = await async_playwright().start()
            
            # Configure browser launch options with proxy if available
            # Use headless=False when using proxy to avoid bot detection
            launch_options = {"headless": False }
            if self.proxy_config:
                launch_options["proxy"] = self.proxy_config.get_playwright_proxy()
            
            self.browser = await playwright.chromium.launch(**launch_options)
        
        # Always create a new page for fresh captcha solving
        if self.page:
            await self.page.close()
        self.page = await self.browser.new_page()
    
    async def _solve_captcha(self) -> str:
        """Solve the captcha via web automation and extract token"""
        await self._init_browser()
        
        # Clear any existing cookies/cache for fresh start
        await self.page.context.clear_cookies()
        
        # Store the token when we intercept the network response
        captured_token = None
        
        async def handle_response(response):
            nonlocal captured_token
            # Intercept the captcha-verify response to get the token
            if 'captcha-verify' in response.url:
                try:
                    data = await response.json()
                    if data.get('token'):
                        captured_token = data['token']
                        logger.info("Captured token from network response")
                except Exception as e:
                    logger.debug(f"Could not parse response from {response.url}: {e}")
        
        # Set up response interception
        self.page.on('response', handle_response)
        
        # Navigate to the appointment page
        url = "https://stadt.muenchen.de/buergerservice/terminvereinbarung.html#/services/10339027/locations/10187259"
        await self.page.goto(url)
        
        # Wait for captcha element to be visible (30 seconds)
        await self.page.wait_for_selector('input[id="altcha_checkbox"]', timeout=30000)
        
        # Click the captcha checkbox - this will trigger the API calls
        await self.page.click('input[id="altcha_checkbox"]')
        
        # Wait for captcha to be solved by the webpage (60 seconds for processing)
        await self.page.wait_for_selector('[data-state="verified"]', timeout=60000)
        
        # Give a moment for the network request to complete
        await asyncio.sleep(2)
        
        # Remove the response listener
        try:
            self.page.remove_listener('response', handle_response)
        except Exception:
            pass  # Ignore if listener was already removed
        
        if captured_token:
            self.current_token = captured_token
            self.token_expires_at = datetime.now() + timedelta(minutes=5)
            logger.info(f"Successfully obtained captcha token")
            return captured_token
        else:
            # Fallback: try to extract from page context
            token = await self.page.evaluate("""
                () => {
                    // Try various ways to get the token from the page
                    return localStorage.getItem('captchaToken') || 
                           sessionStorage.getItem('captchaToken') ||
                           window.captchaToken ||
                           document.querySelector('[data-captcha-token]')?.getAttribute('data-captcha-token');
                }
            """)
            
            if token:
                self.current_token = token
                self.token_expires_at = datetime.now() + timedelta(minutes=5)
                return token
            else:
                raise Exception("Could not extract captcha token after solving")
    
    
    async def _get_current_ip(self, client) -> str:
        """Get current IP address for logging"""
        try:
            response = await client.get("https://httpbin.org/ip", timeout=10.0)
            ip_data = response.json()
            return ip_data.get("origin", "unknown")
        except Exception:
            return "unknown"
    
    async def _check_appointments(self) -> Optional[str]:
        """Check for appointment availability"""
        try:
            # Ensure we have a valid token
            if not self._is_token_valid():
                logger.info("Token expired or invalid, refreshing...")
                await self._cleanup_browser_state()
                await self._solve_captcha()
            
            # Make the appointment availability request
            start_date = datetime.now().strftime("%Y-%m-%d")
            end_date = (datetime.now() + timedelta(days=180)).strftime("%Y-%m-%d")
            
            url = f"{self.base_url}/available-days-by-office/"
            params = {
                'startDate': start_date,
                'endDate': end_date,
                'officeId': self.office_id,
                'serviceId': self.service_id,
                'serviceCount': '1',
                'captchaToken': self.current_token
            }
            
            # Create httpx client with proxy if configured
            client_kwargs = {}
            if self.proxy_config:
                client_kwargs['proxy'] = self.proxy_config.get_httpx_proxy_url()
                # Keep SSL verification enabled - BotProxy should handle SSL properly
            
            async with httpx.AsyncClient(**client_kwargs) as client:
                # Log current IP address for monitoring
                current_ip = await self._get_current_ip(client)
                proxy_status = "via proxy" if self.proxy_config else "direct connection"
                logger.info(f"Making appointment request from IP: {current_ip} ({proxy_status})")
                
                response = await client.get(url, headers=self.headers, params=params)
                data = response.json()
                
                # Check if appointments are available
                if "errors" not in data and data:
                    return f"Available dates: {data}"
                elif "errors" in data:
                    error = data["errors"][0]
                    if error["errorCode"] == "noAppointmentForThisDay":
                        return None
                    else:
                        raise Exception(f"API Error: {error['errorMessage']}")
                else:
                    return None
                    
        except Exception as e:
            logger.error(f"Error checking appointments: {e}")
            await self._cleanup_browser_state()
            
            # For single checks, re-raise the exception
            # For monitoring, we'll handle this in the monitoring loop
            raise
    
    def run(self):
        """Run the bot"""
        logger.info("Starting Munich Appointment Bot...")
        try:
            self.application.run_polling()
        except KeyboardInterrupt:
            logger.info("Shutting down bot...")
        finally:
            if self.browser:
                asyncio.run(self.browser.close())

def main():
    import os
    
    # Get Telegram bot token from environment
    token = os.getenv("TELEGRAM_BOT_TOKEN", "8302207568:AAHihP2Ak_TXpMR8HLrhubGUwZYtw1AUZ2s")
    if not token:
        raise ValueError("Please set TELEGRAM_BOT_TOKEN environment variable")
    
    # Get proxy credentials from environment
    proxy_user = os.getenv("BOTPROXY_USER")
    proxy_password = os.getenv("BOTPROXY_PASSWORD")
    
    if proxy_user and proxy_password:
        logger.info("Using BotProxy for requests")
        bot = MunichAppointmentBot(token, proxy_user=proxy_user, proxy_password=proxy_password)
    else:
        logger.info("No proxy credentials found, running without proxy")
        bot = MunichAppointmentBot(token)
    
    bot.run()

if __name__ == "__main__":
    main()