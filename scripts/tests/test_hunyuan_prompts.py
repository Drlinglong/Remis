import requests
import json

def test_hunyuan_prompt_engineering():
    url = "http://localhost:8000/v1/chat/completions"
    headers = {"Content-Type": "application/json"}
    
    # The text that was causing verbose output
    source_text = "Increase Convoy Contribution"
    
    # 1. Old Prompt (Baseline)
    old_prompt = f"把下面的文本翻译成Simplified Chinese，不要额外解释。\n\n{source_text}"
    
    # 2. New Prompt (With Examples/Few-Shot)
    new_prompt = (
        "你是一个游戏汉化专家。请直接给出最简练的中文翻译，不要添加任何括号、解释或备注。\n\n"
        "示例：\n"
        "原文：Convoy Raiding\n"
        "译文：袭击船队\n\n"
        "原文：Market Access\n"
        "译文：市场接入度\n\n"
        f"原文：{source_text}\n"
        "译文："
    )

    prompts = [
        ("Baseline (Current Logic)", old_prompt),
        ("Few-Shot (Optimized)", new_prompt)
    ]

    print(f"Testing Prompt Variations against Local Hunyuan-MT...\n")

    for name, prompt in prompts:
        data = {
            "model": "hunyuan",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.7,
            "max_tokens": 100
        }
        
        try:
            response = requests.post(url, headers=headers, json=data)
            response.raise_for_status()
            result = response.json()['choices'][0]['message']['content'].strip()
            print(f"--- {name} ---")
            print(f"Prompt:\n{prompt}")
            print(f"\nResult: {result}")
            print("-" * 40 + "\n")
        except Exception as e:
            print(f"Error testing {name}: {e}")

if __name__ == "__main__":
    test_hunyuan_prompt_engineering()
