# TEST

vllm serve in 4090 x4
```
vllm serve --host 0.0.0.0 Qwen/Qwen2.5-72B-Instruct-AWQ  --speculative_model Qwen/Qwen2.5-14B-Instruct-AWQ --num_speculative_tokens 16 --gpu_memory_utilization 0.95 --tensor-parallel-size 4 --max_model_len 8192
```

vllm serve in 4090 x1
```
CUDA_VISIBLE_DEVICES="3" vllm serve --host 0.0.0.0 Qwen/Qwen2.5-14B-Instruct-AWQ  --speculative_model Qwen/Qwen2.5-7B-Instruct-AWQ --num_speculative_tokens 16 --gpu_memory_utilization 0.95 --tensor-parallel-size 1 --max_model_len 8192
```