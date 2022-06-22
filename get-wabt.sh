#!/bin/bash

# shell script to pull the particular version of wabt which
# contains the particular version of wasm2c which makes wasm2native
# work with SPEC

wget -nc https://github.com/WebAssembly/wabt/releases/download/1.0.20/wabt-1.0.20-ubuntu.tar.gz
tar -xzf wabt-1.0.20-ubuntu.tar.gz
