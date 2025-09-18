# Munich Appointment Bot 🤖

A Telegram bot that monitors Munich appointment availability and notifies you when spots become available.

## Features

- **Real-time Monitoring**: Continuously checks for appointment availability
- **Telegram Notifications**: Instant notifications when appointments are found
- **Captcha Solving**: Automatically handles ALTCHA captcha verification
- **Flexible Scheduling**: Configure check intervals (minutes)
- **Health Monitoring**: Check bot status and token validity

## Bot Commands

| Command | Description | Example |
|---------|-------------|---------|
| `/start` | Initialize the bot | `/start` |
| `/help` | Show available commands | `/help` |
| `/health` | Check bot status | `/health` |
| `/single` | Check for appointments once | `/single` |
| `/regular <minutes>` | Start regular monitoring | `/regular 5` |
| `/stop` | Stop regular monitoring | `/stop` |

## Setup Instructions

### 1. Install Dependencies

```bash
# Run the setup script
python setup_bot.py
```

Or manually:
```bash
# Install Python packages
pip install -r requirements_bot.txt

# Install Playwright browsers
python -m playwright install chromium
```

### 2. Create Telegram Bot

1. Message [@BotFather](https://t.me/botfather) on Telegram
2. Send `/newbot` and follow instructions
3. Copy the bot token

### 3. Configure Environment

```bash
# Copy environment template
cp .env.template .env

# Edit .env and add your bot token
TELEGRAM_BOT_TOKEN=your_token_here
```

### 4. Run the Bot

```bash
python appointment_bot.py
```

## How It Works

### Captcha Flow
1. **Page Load**: Bot navigates to appointment page
2. **Captcha Details**: Fetches captcha configuration
3. **Challenge**: Gets proof-of-work challenge
4. **Solving**: Computes SHA-256 hash solution
5. **Verification**: Submits solution for token
6. **Token**: Receives 5-minute valid JWT token

### API Endpoints
- `GET /captcha-details/` - Get captcha configuration
- `GET /captcha-challenge/` - Get proof-of-work challenge  
- `POST /captcha-verify/` - Verify captcha solution
- `GET /available-days-by-office/` - Check appointment availability

### Monitoring Process
1. **Token Check**: Validates JWT token (5min expiry)
2. **Refresh**: Renews token if expired
3. **API Call**: Queries appointment availability
4. **Notification**: Sends Telegram message if spots found
5. **Loop**: Repeats at configured interval

## Configuration

### Appointment Settings
```python
office_id = "10187259"     # Munich office location
service_id = "10339027"    # Service type
```

### Monitoring Settings
- **Default Interval**: 5 minutes
- **Token Expiry**: 5 minutes
- **Date Range**: Next 180 days

## Error Handling

- **Captcha Failures**: Automatic retry with fresh browser session
- **Token Expiry**: Automatic renewal before API calls
- **Network Errors**: Retry with exponential backoff
- **Rate Limiting**: Respects API limits

## Security Features

- **Headless Browser**: No GUI, runs in background
- **Token Management**: Secure JWT token handling
- **Rate Limiting**: Prevents API abuse
- **Error Logging**: Comprehensive logging for debugging

## Troubleshooting

### Common Issues

**Bot doesn't respond**
- Check Telegram token in `.env`
- Verify bot is running: `/health`

**Captcha fails**
- Browser might be detected
- Try different User-Agent
- Check network connectivity

**No appointments found**
- Service may be fully booked
- Try different date range
- Verify office_id and service_id

### Logs
Check console output for detailed error messages and debugging information.

## Monitoring Service Details

**Target**: Munich Bürgerservice
**URL**: https://stadt.muenchen.de/buergerservice/terminvereinbarung.html
**Service**: ID 10339027 (specific service type)
**Office**: ID 10187259 (specific location)

The bot automatically handles:
- ALTCHA captcha solving
- JWT token management
- API rate limiting
- Error recovery
- Notification delivery