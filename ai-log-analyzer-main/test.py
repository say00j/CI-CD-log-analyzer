import requests
import json

URL = "http://localhost:11434/api/chat"
MODEL = "llama3"

messages = []

while True:
    user = input("You: ")
    if user.lower() in ("exit", "quit"):
        break

    messages.append({"role": "user", "content": user})

    response = requests.post(
        URL,
        json={
            "model": MODEL,
            "messages": messages,
            "stream": True
        },
        stream=True,
        timeout=120
    )

    response.raise_for_status()

    print("LLaMA: ", end="", flush=True)

    assistant_reply = ""

    for line in response.iter_lines():
        if not line:
            continue

        data = json.loads(line.decode("utf-8"))

        # Ollama streams partial message content
        if "message" in data and "content" in data["message"]:
            token = data["message"]["content"]
            print(token, end="", flush=True)
            assistant_reply += token

        # Stop condition
        if data.get("done", False):
            break

    print()  # newline after response

    messages.append({"role": "assistant", "content": assistant_reply})
