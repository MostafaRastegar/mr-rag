FROM hub.hamdocker.ir/python:3.13-slim

WORKDIR /app

# RUN apt-get update && apt-get install -y --no-install-recommends \
#     gcc \
#     && rm -rf /var/lib/apt/lists/*

# ---------------------------------------------------------------
# Step 1: Install ALL Python dependencies via pip
# ---------------------------------------------------------------
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# ---------------------------------------------------------------
# Step 2: Copy source code
# ---------------------------------------------------------------
COPY app/ ./app/

EXPOSE 8080

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]