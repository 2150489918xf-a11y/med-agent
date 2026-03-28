#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Quick smoke test for the MCP Vision engine."""

import os
import sys
import json

SERVICE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SERVICE_DIR)
sys.path.insert(0, os.path.join(PROJECT_ROOT, "torchxrayvision"))
sys.path.insert(0, SERVICE_DIR)

from engine import analyze, get_densenet_probs

TEST_IMG = os.path.join(PROJECT_ROOT, "torchxrayvision", "tests", "pneumonia_test.jpg")

if __name__ == "__main__":
    img = sys.argv[1] if len(sys.argv) > 1 else TEST_IMG
    print(f"Testing engine with: {img}")

    print("\n--- DenseNet Classification ---")
    probs = get_densenet_probs(img)
    for k, v in list(probs.items())[:5]:
        print(f"  {k}: {v}")

    print("\n--- Full Analysis ---")
    result = analyze(img, enable_sam=False)
    print(json.dumps(result, ensure_ascii=False, indent=2))

    print("\n✅ Engine smoke test passed!")
