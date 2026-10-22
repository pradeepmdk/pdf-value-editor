# Container for Hugging Face Spaces (Docker SDK) or any container host.
FROM python:3.12-slim

RUN useradd -m -u 1000 user
WORKDIR /app

COPY requirements.txt .
# rapidocr pulls the GUI build of OpenCV, which needs X11/GL libraries; swap in the headless build.
RUN pip install --no-cache-dir -r requirements.txt \
    && pip uninstall -y opencv-python \
    && pip install --no-cache-dir opencv-python-headless

COPY --chown=user *.py *.html *.js ./
COPY --chown=user prompts ./prompts
USER user

# Spaces sets SPACE_HOST (e.g. user-space.hf.space); browsers post from that origin.
# Set OPEN_ROUTER_KEY, SIGNING_SECRET and APP_PASSWORD as host secrets.
ENV PORT=7860
EXPOSE 7860
CMD python pdf_editor.py --host 0.0.0.0 --port "$PORT" --allowed-origin "https://${SPACE_HOST:-localhost}"
