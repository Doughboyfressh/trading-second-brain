from src.llm import TradingLLM
from src.rag_memory import RAGMemory
from src.vault_manager import VaultManager

class BaseAgent:
    def __init__(self, name: str, system_prompt: str):
        self.name = name
        self.llm = TradingLLM()
        self.rag = RAGMemory()
        self.vault = VaultManager()
        self.system_prompt = system_prompt
    
    def think_and_write(self, task: str, folder: str, filename: str):
        context = self.rag.retrieve(task)
        user_prompt = f"Context from brain:\n{context}\n\nTask: {task}\nRespond with structured markdown ready to save."
        response = self.llm.query(self.system_prompt, user_prompt)
        self.vault.write_note(folder, filename, response)
        return response