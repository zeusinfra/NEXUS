#!/usr/bin/env python3
"""
Compile gRPC definitions for NEXUS OS.
Bridges Rust Core with Python Cognitive Engine.
"""

import os
from grpc_tools import protoc

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROTO_DIR = os.path.join(BASE_DIR, "../communication")
PYTHON_OUT_DIR = os.path.join(BASE_DIR, "../cognitive-python/stubs")

os.makedirs(PYTHON_OUT_DIR, exist_ok=True)

protoc.main(
    (
        "",
        "-I" + PROTO_DIR,
        f"--python_out={PYTHON_OUT_DIR}",
        f"--grpc_python_out={PYTHON_OUT_DIR}",
        os.path.join(PROTO_DIR, "nexus_core.proto"),
    )
)

print(f"✅ gRPC stubs generated in {PYTHON_OUT_DIR}")
