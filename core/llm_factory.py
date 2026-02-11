import os
import requests
import json
import time
from abc import ABC, abstractmethod
from typing import Optional, Dict

class AIProvider(ABC):
    @abstractmethod
    def summarize(self, text: str) -> str:
        pass

class OpenAIProvider(AIProvider):
    """
    Generic Provider for API compatible with OpenAI (ZhipuAI, DeepSeek, Moonshot, etc.)
    """
    def __init__(self, api_key: str, base_url: str, model: str, system_prompt: str = None):
        self.api_key = api_key
        self.base_url = base_url.rstrip('/')
        self.model = model
        self.system_prompt = system_prompt or "You are a helpful assistant. Please summarize the following text into a concise Chinese summary (within 100 words)."

    def summarize(self, text: str) -> str:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": text}
            ],
            "max_tokens": 500,
            "temperature": 0.3
        }
        
        try:
            url = f"{self.base_url}/chat/completions"
            response = requests.post(url, headers=headers, json=payload, timeout=30)
            response.raise_for_status()
            res_json = response.json()
            return res_json['choices'][0]['message']['content'].strip()
        except Exception as e:
            print(f"[LLM] OpenAI/Zhipu Request Failed: {e}")
            return ""

class GeminiProvider(AIProvider):
    """
    Provider for Google Gemini API
    """
    def __init__(self, api_key: str, model: str = "gemini-1.5-flash", base_url: str = None, proxy: str = None):
        self.api_key = api_key
        self.model = model
        # Default: https://generativelanguage.googleapis.com/v1beta/models/
        self.base_url = base_url or "https://generativelanguage.googleapis.com/v1beta/models"
        self.proxy = {'https': proxy} if proxy else None

    def summarize(self, text: str) -> str:
        url = f"{self.base_url}/{self.model}:generateContent?key={self.api_key}"
        headers = {"Content-Type": "application/json"}
        payload = {
            "contents": [{
                "parts": [{"text": f"Please summarize the following text into a concise Chinese summary (within 100 words):\n\n{text}"}]
            }]
        }
        
        try:
            response = requests.post(url, headers=headers, json=payload, proxies=self.proxy, timeout=30)
            response.raise_for_status()
            res_json = response.json()
            # Gemini response structure
            try:
                return res_json['candidates'][0]['content']['parts'][0]['text'].strip()
            except (KeyError, IndexError):
                print(f"[LLM] Gemini Invalid Response: {res_json}")
                return ""
        except Exception as e:
            print(f"[LLM] Gemini Request Failed: {e}")
            return ""

class LLMFactory:
    @staticmethod
    def create_provider(config: Dict[str, str]) -> Optional[AIProvider]:
        provider_type = config.get('provider', 'zhipu').lower()
        api_key = config.get('api_key')
        
        if not api_key:
            print("[LLM] No API Key found.")
            return None

        if provider_type == 'zhipu' or provider_type == 'openai':
            # Defaults for Zhipu
            base_url = config.get('base_url') or "https://open.bigmodel.cn/api/paas/v4"
            model = config.get('model') or "glm-4-flash"
            return OpenAIProvider(api_key, base_url, model)
            
        elif provider_type == 'gemini':
            base_url = config.get('base_url') # Optional override for CF Worker
            model = config.get('model') or "gemini-1.5-flash"
            proxy = config.get('proxy')
            return GeminiProvider(api_key, model=model, base_url=base_url, proxy=proxy)
            
        return None
