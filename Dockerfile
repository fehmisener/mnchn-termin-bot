# Use official Playwright Python image (includes all dependencies)
FROM mcr.microsoft.com/playwright/python:v1.55.0-noble

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY appointment_bot.py .
COPY README.md .

# Create non-root user for security
RUN useradd --create-home --shell /bin/bash app && chown -R app:app /app
USER app

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Health check
HEALTHCHECK --interval=5m --timeout=10s --start-period=30s --retries=3 \
    CMD python -c "import asyncio; print('Bot is running')" || exit 1

# Run the bot
CMD ["python", "appointment_bot.py"]