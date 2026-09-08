"""Detects which compute devices actually work for inference.

`torch.cuda.is_available()` only confirms the driver/runtime handshake
succeeded — it does not guarantee a kernel actually launches correctly on
a given device (driver too old for the CUDA build, unsupported compute
capability, etc.). We run a tiny real op on each candidate device and
drop any that fail, so the app degrades to CPU instead of crashing mid
inference when a machine's GPU isn't actually usable.
"""
import torch


def list_working_devices():
    """Return (devices, warnings): `devices` always includes "cpu" plus
    every "cuda:N" that passed a real smoke test; `warnings` maps any
    rejected "cuda:N" to the error that ruled it out."""
    devices = ["cpu"]
    warnings = {}

    if not torch.cuda.is_available():
        return devices, warnings

    for i in range(torch.cuda.device_count()):
        name = f"cuda:{i}"
        try:
            t = torch.zeros(1, device=name)
            _ = (t + 1).cpu()
            devices.append(name)
        except Exception as e:
            warnings[name] = str(e)

    return devices, warnings
