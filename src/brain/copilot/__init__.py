"""Level 3a — the Ask-Anything Copilot's answer engine (hybrid GraphRAG).

  retrieve.py   : find what the question is about, then pull matching passages
                  (by meaning) AND the connected facts (from the graph)
  confidence.py : build a confidence score from several signals (not the LLM's guess)
  answer.py     : write a grounded answer with inline citations
  engine.py     : ask(question) -> answer + sources + confidence
"""
