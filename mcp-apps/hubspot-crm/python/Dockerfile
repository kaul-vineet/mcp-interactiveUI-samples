# Build from hubspot-crm/python/ as context: docker build -t hs-mcp-copilot .

# ── Widget build stage ──────────────────────────────────────────────────────
FROM node:20-slim AS widget-builder
WORKDIR /build
COPY widgets/ widgets/
WORKDIR /build/widgets
RUN npm install && npm run build

# ── Python build stage ──────────────────────────────────────────────────────
FROM python:3.11-slim AS builder
WORKDIR /build
COPY shared_mcp/ shared_mcp/
COPY hs_crm_mcp/ hs_crm_mcp/
COPY web/ web/
COPY pyproject.toml pyproject.toml
# Overlay freshly-built widget.html
COPY --from=widget-builder /build/web/widget.html web/widget.html
RUN pip install --no-cache-dir --prefix=/opt/venv .

# ── Runtime image ───────────────────────────────────────────────────────────
FROM python:3.11-slim AS runtime
COPY --from=builder /opt/venv /opt/venv
COPY --from=builder /build/shared_mcp /opt/venv/lib/python3.11/site-packages/shared_mcp
# web/ lives one level up from hs_crm_mcp — mirror that for Path(__file__).parent.parent / "web"
COPY --from=builder /build/web /opt/venv/lib/python3.11/site-packages/web
ENV PATH="/opt/venv/bin:$PATH" PYTHONPATH="/opt/venv/lib/python3.11/site-packages"
ENV PYTHONUNBUFFERED=1
EXPOSE 8082
CMD ["python", "-m", "hs_crm_mcp"]
