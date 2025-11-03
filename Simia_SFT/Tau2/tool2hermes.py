#!/usr/bin/env python3
"""
Convert JSON format function calls to Hermes format and adjust roles:
- function_call -> gpt (using Hermes format)
- observation -> human
"""

import json
import argparse
import re
from typing import List, Dict, Any, Optional


def convert_json_to_hermes_format(function_call_json: str) -> Optional[str]:
    """
    Convert JSON format function call to Hermes format.
    Supports two input formats:
    1. Pure JSON: {"name": "xxx", "arguments": {...}}
    2. Think + JSON: <think>xxx</think>\n{"name": "xxx", "arguments": {...}}
    """
    try:

        think_content = ""
        json_part = function_call_json.strip()
        
        if "<think>" in function_call_json and "</think>" in function_call_json:

            think_match = re.search(r'<think>(.*?)</think>\s*(.*)', function_call_json, re.DOTALL)
            if think_match:
                think_content = f"<think>{think_match.group(1)}</think>\n"
                json_part = think_match.group(2).strip()

        call_data = json.loads(json_part)
        name = call_data.get("name", "")
        arguments = call_data.get("arguments", {})
        tool_call_data = {"name": name, "arguments": arguments}
        hermes_format = f"{think_content}<tool_call>\n{json.dumps(tool_call_data)}\n</tool_call>\n"
        return hermes_format
    except json.JSONDecodeError:
        return None


def convert_conversations(conversations: List[Dict[str, str]]) -> Optional[List[Dict[str, str]]]:
    """Convert conversation list, return None if JSON parsing error occurs"""
    converted = []
    
    for turn in conversations:
        from_role = turn["from"]
        value = turn["value"]
        
        if from_role == "function_call":
            hermes_value = convert_json_to_hermes_format(value)
            if hermes_value is None:
                return None
            converted.append({"from": "gpt", "value": hermes_value})
        elif from_role == "observation":
            converted.append({"from": "human", "value": value})
        else:
            converted.append(turn)
    
    return converted


def process_dataset(input_file: str, output_file: str):
    """Process the entire dataset"""
    print(f"Processing: {input_file}")
    
    with open(input_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    converted_data = []
    deleted_count = 0
    for i, item in enumerate(data):
        if (i + 1) % 1000 == 0:
            print(f"Progress: {i + 1}/{len(data)}")
        
        if "conversations" in item:
            converted_conversations = convert_conversations(item["conversations"])
            if converted_conversations is not None:
                converted_item = item.copy()
                converted_item["conversations"] = converted_conversations
                converted_data.append(converted_item)
            else:
                deleted_count += 1
        else:
            converted_data.append(item)
    
    print(f"Total: {len(data)}, Kept: {len(converted_data)}, Deleted: {deleted_count}")
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(converted_data, f, ensure_ascii=False, indent=2)
    
    print(f"Saved to: {output_file}")


def main():
    parser = argparse.ArgumentParser(description="Convert JSON function calls to Hermes format")
    parser.add_argument("--input", "-i", required=True, help="Input file path")
    parser.add_argument("--output", "-o", help="Output file path (default: input_hermes.json)")
    
    args = parser.parse_args()
    
    if not args.output:
        input_name = args.input.rsplit('.', 1)[0]
        args.output = f"{input_name}_hermes.json"
    
    process_dataset(args.input, args.output)


if __name__ == "__main__":
    import sys
    import os
    if len(sys.argv) == 1:
        input_file = ""
        output_file = ""
        process_dataset(input_file, output_file)
    else:
        main()