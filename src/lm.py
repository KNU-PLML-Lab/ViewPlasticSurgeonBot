from huggingface_hub import hf_hub_download
from vllm import LLM, SamplingParams
import json
from pathlib import Path
from typing import Optional, Union
import os



def run_gguf_inference(
  model_path: str,
  tokenizer_path: str,
):
  # PROMPT_TEMPLATE = "<|system|>\n{system_message}</s>\n<|user|>\n{prompt}</s>\n<|assistant|>\n"  # noqa: E501
  # system_message = "You are a friendly chatbot who always responds in the language of the person who spoke to you."  # noqa: E501
  # # Sample prompts.
  # prompts = [
  #   # "How many helicopters can a human eat in one sitting?",
  #   # "What's the future of AI?",
  #   "한 사람이 한 번에 먹을 수 있는 헬리콥터는 몇 대인가요?"
  # ]
  # prompts = [
  #   PROMPT_TEMPLATE.format(system_message=system_message, prompt=prompt)
  #   for prompt in prompts
  # ]
  messages = [
    {"role": "system", "content": "You are a friendly chatbot who always responds in the language of the person who spoke to you."},
    {"role": "user", "content": "Hello, how are you?"},
    {"role": "assistant", "content": "I'm doing well, thank you!"},
    {"role": "user", "content": "한 사람이 한 번에 먹을 수 있는 헬리콥터는 몇 대인가요?"}
  ]
  # Create a sampling params object.
  sampling_params = SamplingParams(
    temperature=0,
    max_tokens=128,
  )

  # Create an LLM.
  llm = LLM(
    model=model_path,
    tokenizer=tokenizer_path,
    gpu_memory_utilization=0.95,
  )

  # outputs = llm.generate(prompts, sampling_params)
  res = llm.chat(
    messages=messages,
    sampling_params=sampling_params,

  )
  print(res)
  # Print the outputs.
  # for output in outputs:
  #   prompt = output.prompt
  #   generated_text = output.outputs[0].text
  #   print(f"Prompt: {prompt!r}, Generated text: {generated_text!r}")



if __name__ == "__main__":
  model_model = hf_hub_download(
    "gphorvath/Ministral-8B-Instruct-2410-Q4_K_M-GGUF",
    filename="ministral-8b-instruct-2410-q4_k_m.gguf",
    cache_dir="./hf_cache"
  )
  model_tokenizer = hf_hub_download(
    "mistralai/Ministral-8B-Instruct-2410",
    filename="tokenizer.json",
    cache_dir="./hf_cache"
  )
  model_tokenizer_config = hf_hub_download(
    "mistralai/Ministral-8B-Instruct-2410",
    filename="tokenizer_config.json",
    cache_dir="./hf_cache"
  )
  model_tokenizer_dir = os.path.dirname(model_tokenizer)

  run_gguf_inference(
    model_path=model_model,
    tokenizer_path=model_tokenizer_dir
  )

class VpsbLmServer:
  """
    뷰성형외과 봇의 언어모델을 관리 클래스
  """
  def __init__(
    self,
    model_path: str = None,
    tokenizer_path: str = None,
  ):
    # 모델 로드 및 환경 변수 설정
    if model_path is not None:
      self.model_path = model_path
    else:
      self.model_path = hf_hub_download(
        "gphorvath/Ministral-8B-Instruct-2410-Q4_K_M-GGUF",
        filename="ministral-8b-instruct-2410-q4_k_m.gguf",
        cache_dir="./hf_cache"
      )
    if tokenizer_path is not None:
      self.tokenizer_config_path = None
      self.tokenizer_path = tokenizer_path
    else:
      self.tokenizer_config_path = hf_hub_download(
        "mistralai/Ministral-8B-Instruct-2410",
        filename="tokenizer_config.json",
        cache_dir="./hf_cache"
      )
      self.tokenizer_path = hf_hub_download(
        "mistralai/Ministral-8B-Instruct-2410",
        filename="tokenizer.json",
        cache_dir="./hf_cache"
      )
    
    self.system_message = "You are a friendly chatbot who always responds in the language of the person who spoke to you."
    
    # vllm 초기화
    self.llm = LLM(
      model=self.model_path,
      tokenizer=self.tokenizer_path,
      gpu_memory_utilization=0.95,
    )
    self.sampling_params = SamplingParams(
      temperature=0,
      max_tokens=128,
    )

