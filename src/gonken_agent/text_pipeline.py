"""Executable grounded text path for host validation before voice activation."""
import time
from .retrieval.index import load, retrieve
from .llm.prompts import abstain, extractive, messages, validate_answer


class TextPipeline:
    def __init__(self, index_path, corpus, *, client=None, top_k=3, telemetry=None, snapshot=None):
        self.index_path,self.corpus = index_path,corpus
        self.client,self.top_k = client,top_k
        self.telemetry,self.snapshot = telemetry,snapshot
        self.index = load(index_path,corpus)
        self.identity = None
        self.started = 0.0
    def ready(self): return True  # Readiness is for this explicit text diagnostic path only.
    def retrieve(self,text,cancel):
        self.started = time.monotonic()
        self.index = load(self.index_path,self.corpus)  # reject corpus drift before each interaction
        return retrieve(self.index,text,self.top_k)
    def generate(self,text,hits,cancel):
        if not hits:
            answer = abstain()
        elif self.client is None:
            answer = extractive(hits)
        else:
            self.identity = self.client.model_identity(cancel)
            answer = validate_answer(self.client.chat(messages(text,hits),cancel),hits)
        metrics = {'state':'IDLE','status':'READY','source_ids':list(answer.source_ids),
                   'duration_ms':round((time.monotonic()-self.started)*1000,3)}
        if self.identity: metrics.update(self.identity)
        if self.telemetry: self.telemetry.append(metrics)
        if self.snapshot: self.snapshot.update(metrics,transcript=text,answer=answer.answer)
        return answer
    def close(self):
        if self.client: self.client.close()
        if self.snapshot: self.snapshot.clear()
