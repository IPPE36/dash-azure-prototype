# src/worker/config.py

from shared.env import env_str, get_int_env

TORCH_NUM_THREADS = get_int_env("TORCH_NUM_THREADS", default=1, min_value=1)
TORCH_NUM_INTEROP_THREADS = get_int_env("TORCH_NUM_INTEROP_THREADS", default=1, min_value=1)
TORCH_MATMUL_PRECISION = env_str("TORCH_MATMUL_PRECISION", default="")
TORCH_DEVICE = env_str("TORCH_DEVICE", default="cpu")
MODEL_PATH = env_str("MODEL_PATH", default="/app/models/model.pt")
