FROM python:3.12-slim

WORKDIR /app

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    STREAMLIT_SERVER_PORT=8501 \
    STREAMLIT_SERVER_ADDRESS=0.0.0.0 \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false

# Install curl and system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy project files
COPY pyproject.toml README.md CHANGELOG.md LICENSE /app/
COPY certified_dose/ /app/certified_dose/
COPY docs/ /app/docs/

# Install the package and dashboard dependencies
RUN pip install --upgrade pip && \
    pip install .[dashboard]

# Expose Streamlit port
EXPOSE 8501

# Healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl --fail http://localhost:8501/_stcore/health || exit 1

# Default command: launch the interactive dashboard
ENTRYPOINT ["certified-dose"]
CMD ["dashboard", "--port", "8501", "--host", "0.0.0.0"]
