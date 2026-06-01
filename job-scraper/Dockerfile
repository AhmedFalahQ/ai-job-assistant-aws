# Use Microsoft's official Playwright Python image
FROM mcr.microsoft.com/playwright/python:v1.44.0-jammy

# Install Lambda runtime interface client
RUN pip install --no-cache-dir awslambdaric

# Copy and install Python dependencies including Playwright
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browsers explicitly for our pip-installed version
RUN python -m playwright install chromium

# Set working directory
WORKDIR /var/task

# Copy Lambda handler
COPY handler.py .

# Lambda entry point via runtime interface client
ENTRYPOINT [ "python", "-m", "awslambdaric" ]
CMD ["handler.lambda_handler"]