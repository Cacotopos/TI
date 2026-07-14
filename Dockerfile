# TI Expansions — Editor & Static Site Generator
# Includes Python dependencies for the editor, site generator, and card_diff OCR.
FROM python:3.12-slim

# Install system dependencies required by Pillow, OpenCV (via EasyOCR), PyTorch, etc.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    libgomp1 \
    gcc \
    git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies first so Docker layer caching works.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the project.
COPY . .

# The editor serves on port 3030.
EXPOSE 3030

ENV PYTHONUNBUFFERED=1
ENV EDITOR_HOST=0.0.0.0
ENV EDITOR_PORT=3030

# Default command runs the local web editor.
CMD ["python", "-m", "expansions.editor.app"]
