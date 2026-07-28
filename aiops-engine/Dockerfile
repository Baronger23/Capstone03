FROM golang:1.26.5@sha256:3aff6657219a4d9c14e27fb1d8976c49c29fddb70ba835014f477e1c70636647 AS kubectl-builder

WORKDIR /src

# Keep the Kubernetes 1.36 command surface while overriding vulnerable transitive
# Go modules until an upstream stable kubectl release contains their fixes.
COPY kubectl-builder/go.mod kubectl-builder/go.sum ./
RUN go mod download
COPY kubectl-builder/main.go ./
RUN CGO_ENABLED=0 GOOS=linux GOARCH=amd64 \
    go build -mod=readonly -trimpath \
    -ldflags="-s -w \
      -X k8s.io/component-base/version.gitMajor=1 \
      -X k8s.io/component-base/version.gitMinor=36 \
      -X k8s.io/component-base/version.gitVersion=v1.36.3-aiops.1 \
      -X k8s.io/component-base/version.gitCommit=0f29094e5b73085e3802ecc1298ecae13866bfe6 \
      -X k8s.io/component-base/version.gitTreeState=clean \
      -X k8s.io/component-base/version.buildDate=2026-07-28T00:00:00Z" \
    -o /out/kubectl .

FROM python:3.10-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY --chmod=0755 --from=kubectl-builder /out/kubectl /usr/local/bin/kubectl

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .

# Grant read/write permissions to non-root user 10001 for S3 model downloads
RUN chown -R 10001:10001 /app

# Expose port 8000
EXPOSE 8000

# Set environment variable defaults
ENV AIOPS_SIMULATION_MODE=false
ENV PORT=8000

# Start Uvicorn server
CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
