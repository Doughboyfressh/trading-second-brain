# src/agents/base.py
from src.llm import TradingLLM
from src.rag_memory import RAGMemory
from src.vault_manager import VaultManager

class BaseAgent:
    def __init__(self, name: str, system_prompt: str,
                 model: str = None,
                 max_tokens: int = 2000,
                 rag_top_k: int = 4,
                 temperature: float = 0.15):
        self.name          = name
        self.llm           = TradingLLM()
        self.rag           = RAGMemory()
        self.vault         = VaultManager()
        self.system_prompt = system_prompt
        self.model         = model or TradingLLM.SONNET
        self.max_tokens    = max_tokens
        self.rag_top_k     = rag_top_k
        self.temperature   = temperature

    def think_and_write(self, task: str, folder: str, filename: str) -> str:
        # Retrieve relevant vault context
        raw_context = self.rag.retrieve(task, top_k=self.rag_top_k)

        # Distribute the token budget fairly across returned documents.
        # all-MiniLM-L6-v2 already truncates at 512 tokens; we further cap each
        # doc so that later high-relevance documents aren't silently dropped by a
        # single [:4000] slice that only cuts from the end of the joined string.
        if raw_context and raw_context != "No relevant memory found.":
            sections    = raw_context.split("\n\n---\n\n")
            per_doc_cap = max(300, 4000 // max(len(sections), 1))
            context = "\n\n---\n\n".join(s[:per_doc_cap] for s in sections)
        else:
            context = "No relevant memory found."

        user_prompt = (
            f"Context from brain:\n{context}\n\n"
            f"Task: {task}\n\n"
            f"Respond with concise, structured markdown ready to save to the vault."
        )
        response = self.llm.query(
            self.system_prompt, user_prompt,
            max_tokens=self.max_tokens,
            model=self.model,
            temperature=self.temperature,
        )
        self.vault.write_note(folder, filename, response)
        return response
