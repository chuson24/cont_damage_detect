# GPU-enabled image for webapp/ (FastAPI web UI). Reuses core/ pipeline
# unchanged. Requires the host to have nvidia-container-toolkit configured
# (docker compose "deploy.resources.reservations.devices" GPU reservation).
FROM nvidia/cuda:12.1.1-cudnn8-runtime-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update && apt-get install -y --no-install-recommends \
        python3 python3-pip libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY webapp/requirements.txt webapp/requirements.txt
RUN pip3 install -r webapp/requirements.txt \
    && pip3 install --index-url https://download.pytorch.org/whl/cu121 torch==2.4.1 torchvision==0.19.1 \
    && pip3 install ultralytics opencv-python-headless numpy

COPY core/ core/
COPY webapp/ webapp/
COPY weights/ weights/

EXPOSE 8000
CMD ["python3", "-m", "uvicorn", "webapp.server:app", "--host", "0.0.0.0", "--port", "8000"]
