# Use Python 3.12 as base image
FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    # WeasyPrint runtime
    libpango-1.0-0 libpangocairo-1.0-0 libcairo2 libjpeg62-turbo libpng16-16 \
    shared-mime-info libxml2-dev libxslt1-dev libffi-dev \
    # OpenCV
    # libgl1-mesa-glx\
    ffmpeg \
    # fonts
    fonts-noto fonts-noto-cjk-extra fonts-noto-color-emoji \
  && fc-cache -f -v \
  && apt-get clean && rm -rf /var/lib/apt/lists/*

# Install required packages
COPY requirements.txt .
RUN pip3 install -U pip setuptools wheel &&\
  pip3 install --no-cache-dir --root-user-action=ignore -r requirements.txt

# Set working directory
WORKDIR /app

# Copy application code
COPY video2article/ /app/video2article/
COPY config.yaml /app/config.yaml

# Create a non-root user and group for running the application
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Change ownership of the application directory
RUN chown -R appuser:appuser /app

# Switch to the non-root user
USER appuser

# Default command
CMD ["python3", "-m", "video2article.main"] 