#!/usr/bin/env python3
"""Prepare a Keras file or recognize a native TensorFlow SavedModel directory.
This is an OFFLINE export step, never part of inference.
"""
import argparse
from pathlib import Path

def main():
    p = argparse.ArgumentParser()
    p.add_argument("model", type=Path)
    p.add_argument("--output", type=Path)
    a = p.parse_args()
    src = a.model.resolve()
    if src.is_dir() and (src / "saved_model.pb").exists():
        print(f"Native SavedModel: {src}")
        return
    if not src.is_file() or src.suffix.lower() != ".keras":
        p.error("Expected .keras file or SavedModel .tf directory")
    if a.output is None:
        a.output = src.parent / (src.stem + ".tf")
    if a.output.exists():
        p.error(f"Output exists: {a.output}; specify a new --output")
    import tensorflow as tf
    model = tf.keras.models.load_model(src, compile=False)
    model.export(str(a.output))
    print("SavedModel exported:", a.output)
    print("Inspect signature: saved_model_cli show --dir", a.output, "--all")

if __name__ == "__main__":
    main()
