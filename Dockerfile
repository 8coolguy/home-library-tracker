FROM python:3.11-slim

# System deps required by PaddleOCR / OpenCV
RUN apt-get update && apt-get install -y --no-install-recommends \
        libglib2.0-0 \
        libsm6 \
        libxrender1 \
        libxext6 \
        libgl1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps first (better layer caching)
COPY pyproject.toml setup.py ./
COPY home_library/ ./home_library/
COPY server/ ./server/

RUN pip install --no-cache-dir ".[server]"

# Pre-download PaddleOCR models so the container doesn't need internet at runtime
RUN python -c "from paddleocr import PaddleOCR; PaddleOCR(use_angle_cls=True, lang='en', show_log=False)"

# Runtime directories (overridden by volumes in docker-compose)
RUN mkdir -p /data /uploads

ENV HOME_LIBRARY_DB=sqlite:////data/home_library.db
ENV HOME_LIBRARY_UPLOADS=/uploads
ENV HOME_LIBRARY_OCR_CONFIDENCE=0.5

EXPOSE 8000

CMD ["uvicorn", "server.app:app", "--host", "0.0.0.0", "--port", "8000"]
