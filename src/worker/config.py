# src/worker/config.py

from shared.env import env_str, get_int_env

TORCH_NUM_THREADS = get_int_env("TORCH_NUM_THREADS", default=1, amin=1)
TORCH_NUM_INTEROP_THREADS = get_int_env("TORCH_NUM_INTEROP_THREADS", default=1, amin=1)
TORCH_MATMUL_PRECISION = env_str("TORCH_MATMUL_PRECISION", default="")
MODEL_REPOSITORY_ROOT_PATH = env_str("MODEL_PATH", default="/app/ml/models/artifacts/")
