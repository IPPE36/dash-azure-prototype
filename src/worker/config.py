# src/worker/config.py

from shared.env import env_str, get_int_env

TORCH_NUM_THREADS = get_int_env("TORCH_NUM_THREADS", min_value=1)
TORCH_NUM_INTEROP_THREADS = get_int_env("TORCH_NUM_INTEROP_THREADS", min_value=1)
TORCH_MATMUL_PRECISION = env_str("TORCH_MATMUL_PRECISION", "")
TORCH_DEVICE = env_str("TORCH_DEVICE", "")
