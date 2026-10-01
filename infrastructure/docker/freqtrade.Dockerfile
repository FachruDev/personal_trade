FROM freqtradeorg/freqtrade:stable
USER root
COPY packages/trading_core /opt/trading_core
RUN pip install --no-cache-dir /opt/trading_core
USER ftuser
