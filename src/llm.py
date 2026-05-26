import ollama

def js(html, instructions):
    return ollama.chat(
        model="qwen2.5-coder:32b",
        messages=[{
            "role": "You are a javascript genuis. Give only javascript code that satisfies the requirements",
            "content": f"""
                Given this html code, return a javascript code that {instructions}.
                Output only the code, nothing else.
                Example Output: document.getElementById("apply-button").click()
                HTML:
                {html}
            """
        }]
    )['message']['content']