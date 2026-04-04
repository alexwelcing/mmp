# Hardhat local node for contract development and Web3 integration testing.

FROM node:20-slim

WORKDIR /app

# Install build tools for native deps (secp256k1, etc).
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    make \
    g++ \
    git \
    && rm -rf /var/lib/apt/lists/*

# Cache npm install by copying package files first.
COPY package.json package-lock.json* ./
RUN npm install --legacy-peer-deps

# Copy contract source and build artifacts.
COPY . .

# Default: compile contracts and start the local node.
# The node listens on 0.0.0.0 so it is reachable from other Docker containers.
CMD ["npx", "hardhat", "node", "--hostname", "0.0.0.0", "--port", "8545"]
