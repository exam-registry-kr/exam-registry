#!/bin/sh
# Checks rfc9497.py and transparency_log.py against third-party reference data.
# The data is fetched at fixed commits into a temporary folder and only read as JSON or text.
set -e
DIR=$(mktemp -d)
git clone -q https://github.com/cfrg/draft-irtf-cfrg-voprf.git "$DIR/voprf"
git -C "$DIR/voprf" checkout -q 43da59f797c92248c0362e4c74cc10a8bd2b7b7d
git clone -q https://github.com/cfrg/draft-irtf-cfrg-hash-to-curve.git "$DIR/h2c"
git -C "$DIR/h2c" checkout -q 664b13592116cecc9e52fb192dcde0ade36f904e
git clone -q https://github.com/transparency-dev/merkle.git "$DIR/merkle"
git -C "$DIR/merkle" checkout -q c39fbf350a405f68571bf4c42a6a518eb0a46a4b
mkdir -p "$DIR/vectors"
cp "$DIR/voprf/poc/vectors/allVectors.json" "$DIR/h2c/poc/vectors/P256_XMD:SHA-256_SSWU_RO_.json" "$DIR/vectors/"
cd "$(dirname "$0")"
python3 -I rfc9497.py --check "$DIR/vectors"
python3 -I transparency_log.py --check "$DIR/merkle"
