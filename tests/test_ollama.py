import ollama
try:
    models = ollama.list()
    print("Type of models:", type(models))
    print("Models:", models)
except Exception as e:
    print("Error:", e)
