FROM docker:28-cli
RUN apk add --no-cache python3 py3-yaml
WORKDIR /opt/algotrader
COPY scripts/generate_env.py ./scripts/generate_env.py
COPY config/topology.yaml ./config/topology.yaml
COPY release/installer ./installer
COPY release/compose.yaml ./release/compose.yaml
COPY release/README.md ./README.md
COPY release/docs ./docs
ENTRYPOINT ["python3", "-m", "installer"]
