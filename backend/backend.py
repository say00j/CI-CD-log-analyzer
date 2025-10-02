from flask import Flask, request, Response
from flask_cors import CORS
import requests
import json
import re

# Initialize the Flask application
app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# -----------------------------
# Utility: Extract system info
# -----------------------------
def extract_system_info(log_content):
    info = {}
    
    if "##[group]" in log_content or "actions/checkout" in log_content:
        info['Platform'] = 'GitHub Actions'

    os_match = re.search(r"##\[group\]Operating System\s*\n(.*?)\s*\n([\d\.]+)", log_content)
    if os_match:
        os_name = os_match.group(1).strip()
        os_version = os_match.group(2).strip()
        info['Operating System'] = f"{os_name} {os_version}"

    python_match = re.search(r"Successfully set up CPython \((.*?)\)", log_content)
    if python_match:
        info['Programming Language'] = f"Python ({python_match.group(1).strip()})"
    else:
        python_version_match = re.search(r"python-version:\s*([\d\.]+)", log_content)
        if python_version_match:
            info['Programming Language'] = f"Python ({python_version_match.group(1).strip()})"

    repo_match = re.search(r"repository:\s*([\w/-]+)", log_content)
    if repo_match:
        info['Repository'] = repo_match.group(1).strip()

    git_match = re.search(r"git version ([\d\.]+)", log_content)
    if git_match:
        info['Git Version'] = git_match.group(1).strip()

    return info

# -----------------------------
# Utility: Extract error snippets
# -----------------------------
def extract_error_snippets(lines, error_keywords, context_lines=5):
    pattern_parts = [r'\b' + re.escape(key) + r'\b' for key in error_keywords if key.isalnum()]
    non_alnum_keys = [re.escape(key) for key in error_keywords if not key.isalnum()]
    error_pattern = re.compile('|'.join(pattern_parts + non_alnum_keys), re.IGNORECASE)

    snippets = []
    printed_lines = set()

    for i, line in enumerate(lines):
        if i in printed_lines:
            continue

        if error_pattern.search(line):
            start_index = max(0, i - context_lines)
            end_index = min(len(lines), i + context_lines + 1)
            for j in range(start_index, end_index):
                printed_lines.add(j)

            context_block = lines[start_index:end_index]
            formatted_snippet = f"--- Snippet found around line {i+1} ---\n" + "".join(context_block)
            snippets.append(formatted_snippet)
            
    return snippets

# Comprehensive error keywords
COMPREHENSIVE_KEYWORDS = [
    'error', 'failed', 'failure', 'fatal', 'exception', 'critical', 'panic',
    'unhandled', 'crashed', 'aborted', 'exit code', 'nonzero exit code', '##[error]',
    'build failed', 'compilation error', 'linker error', 'undefined reference',
    'cannot find symbol', 'syntax error', 'make: ***', 'segmentation fault',
    'test failed', 'tests failed', 'assertionerror', '1 failed',
    'expected:', 'but was:', 'spec failed', 'phpunit', 'pytest',
    'npm err!', 'could not resolve dependencies', 'dependency error',
    'packagenotfound', 'modulenotfounderror', 'importerror', 'unresolved import',
    'pip install failed', 'maven execution failed', 'gradle build failed',
    'permission denied', 'access denied', 'unauthorized', 'auth failed',
    'forbidden', '403', '401', 'ssh: handshake failed', 'authentication failed',
    'deployment failed', 'connection refused', 'connection timed out', 'timeout',
    'host not found', 'no route to host', 'service unavailable', '503', '500',
    'internal server error', 'handshake_failure', 'sslerror',
    'command not found', 'invalid argument', 'missing required parameter',
    'yaml syntax error', 'json parse error', 'invalid configuration',
    'no such file or directory', 'file not found', 'ansible failed',
    'out of memory', 'oomkilled', 'no space left on device', 'disk quota exceeded',
    'resource limit exceeded'
]

# -----------------------------
# Stream response from Llama
# -----------------------------
def stream_llama_response(prompt):
    url = "http://localhost:11434/api/generate"
    payload = {
        "model": "llama3.2",
        "prompt": prompt,
        "stream": True
    }

    try:
        with requests.post(url, json=payload, stream=True) as response:
            response.raise_for_status()
            for line in response.iter_lines():
                if line:
                    data = json.loads(line.decode('utf-8'))
                    token = data.get("response", "")
                    yield token
                    if data.get("done"):
                        break
    except Exception as e:
        yield f"\n❌ Error: Could not connect to Ollama. Details: {e}\n"

# -----------------------------
# API Endpoint
# -----------------------------
@app.route("/api/analyze", methods=["POST"])
def analyze():
    user_input = request.form.get('prompt')  # still using 'log' key for now
    #print(request.form.get('prompt'))
    if not user_input:
        return Response("Error: Input text is required.", status=400)

    # Check if input looks like logs (has multiple lines + error keywords)
    looks_like_log = any(word.lower() in user_input.lower() for word in COMPREHENSIVE_KEYWORDS)

    if looks_like_log:
        # Preprocess logs
        system_info = extract_system_info(user_input)
        lines = user_input.splitlines(keepends=True)
        error_snippets = extract_error_snippets(lines, COMPREHENSIVE_KEYWORDS, context_lines=5)

        # Build log-analysis prompt
        prompt_parts = [
            "You are a CI/CD log analyzer. Analyze the following build/test logs.",
            "1. Summarize the key errors and root causes.",
            "2. Suggest possible fixes for each issue.",
            "3. Highlight environment/system info if relevant.",
            "\n--- System Information ---"
        ]
        for k, v in system_info.items():
            prompt_parts.append(f"{k}: {v}")

        prompt_parts.append("\n--- Error Snippets ---")
        if error_snippets:
            prompt_parts.extend(error_snippets[:10])
        else:
            prompt_parts.append("No obvious error snippets found.")

        final_prompt = "\n".join(prompt_parts)
        print(final_prompt)
    else:
        # Treat as normal chat message
        final_prompt = f"{user_input}"

    # Stream response back
    llama_stream = stream_llama_response(final_prompt)
    return Response(llama_stream, mimetype='text/plain')

# -----------------------------
# Run Flask
# -----------------------------
if __name__ == "__main__":
    app.run(debug=True, port=5000)
