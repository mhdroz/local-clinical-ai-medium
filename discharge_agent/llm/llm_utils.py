import requests
import openai
import anthropic
from enum import Enum
from discharge_agent.extractions.prompts import get_user_prompt, system_prompt


class LLMProvider(Enum):
    LOCAL = "local"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"


class MedicalDataExtractor:
    def __init__(self, provider: LLMProvider, **kwargs):
        self.provider = provider
        self.config = kwargs
        self._setup_client()

    def _setup_client(self):
        """Initialize the appropriate client based on provider"""
        if self.provider == LLMProvider.LOCAL:
            self.api_url = self.config.get("api_url", "http://localhost:11434/api/chat")
            self.model = self.config.get("model", "gpt-oss")

        elif self.provider == LLMProvider.OPENAI:
            self.client = openai.OpenAI(api_key=self.config.get("api_key"))
            self.model = self.config.get("model", "gpt-4")

        elif self.provider == LLMProvider.ANTHROPIC:
            self.client = anthropic.Anthropic(api_key=self.config.get("api_key"))
            self.model = self.config.get("model", "claude-3-5-sonnet-20241022")

    def extract_clinical_information(self, note: str, temperature: float = 0.1) -> str:
        """Extract clinical information using the configured provider"""
        system_prompt = self._get_system_prompt()
        user_prompt = self._get_user_prompt(note)

        if self.provider == LLMProvider.LOCAL:
            return self._extract_local(system_prompt, user_prompt, temperature)
        elif self.provider == LLMProvider.OPENAI:
            return self._extract_openai(system_prompt, user_prompt, temperature)
        elif self.provider == LLMProvider.ANTHROPIC:
            return self._extract_anthropic(system_prompt, user_prompt, temperature)

    def _extract_local(
        self, system_prompt: str, user_prompt: str, temperature: float
    ) -> str:
        """Your existing local extraction logic"""
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "stream": False,
            # "options": {"temperature": temperature}
        }
        r = requests.post(self.api_url, json=payload, timeout=120)
        return r.json()["message"]["content"]

    def _extract_openai(
        self, system_prompt: str, user_prompt: str, temperature: float
    ) -> str:
        """OpenAI extraction"""
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            # temperature=temperature,
            # max_completion_tokens=1500
        )
        return response.choices[0].message.content

    def _extract_anthropic(
        self, system_prompt: str, user_prompt: str, temperature: float
    ) -> str:
        """Anthropic extraction"""
        response = self.client.messages.create(
            model=self.model,
            max_tokens=4000,
            temperature=temperature,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        return response.content[0].text

    def _get_system_prompt(self) -> str:
        """Your existing system prompt"""
        return system_prompt

    def _get_user_prompt(self, note: str) -> str:
        """Your existing user prompt logic"""
        return get_user_prompt(note)
