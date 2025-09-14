# llm/helper.py
from typing import List, Dict
from openai import OpenAI

# Import constants from config
from config import OPENAI_API_KEY, CHAT_MODEL, EMBED_MODEL

class LLMHelper:
    def __init__(self):
        self.client = OpenAI(api_key=OPENAI_API_KEY)
        self.chat_model = CHAT_MODEL
        self.embed_model_name = EMBED_MODEL

        print(f"API Service: Using OpenAI chat model: {self.chat_model}")
        print(f"API Service: Using OpenAI embedding model: {self.embed_model_name}")

    def embed_text(self, text: str) -> List[float]:
        try:
            res = self.client.embeddings.create(model=self.embed_model_name, input=text)
            return res.data[0].embedding
        except Exception as e:
            print(f"API Service: Error generating OpenAI embedding: {e}")
            raise

    def chat_with_context(self, system_prompt: str, user_query: str, context_chunks: List[str], history: List[Dict[str, str]] = None, temperature: float = 0.7) -> str:
        messages = [{"role": "system", "content": system_prompt}]
        if context_chunks:
            context_text = "\n\n".join(context_chunks)
            messages.append({"role": "system", "content": f"Context (use this to answer):\n{context_text}"})
        if history:
            for h in history[-2:]:
                messages.append({"role": h["role"], "content": h["content"]})
        messages.append({"role": "user", "content": user_query})
        resp = self.client.chat.completions.create(model=self.chat_model, messages=messages, max_tokens=400, temperature=temperature)
        return resp.choices[0].message.content.strip()

    def rephrase_query(self, user_query: str, history: List[Dict[str, str]]) -> str:
        # Import prompt from prompts.py
        from llm.prompts import REPHRASE_QUERY_PROMPT

        messages = [{"role": "system", "content": REPHRASE_QUERY_PROMPT}]
        for msg in history[-6:]:
            messages.append({"role": msg["role"], "content": msg["content"]})
        messages.append({"role": "user", "content": f"Rewrite this into a standalone question: {user_query}"})
        resp = self.client.chat.completions.create(model=self.chat_model, messages=messages, max_tokens=150)
        return resp.choices[0].message.content.strip()

# Instantiate the LLMHelper globally for the API service
llm_helper = LLMHelper()