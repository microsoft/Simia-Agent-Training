#!/usr/bin/env python3
"""
Process conversation data, clean and fix <think> tags and tool calls.

Rules:
1. If turn has <think> but no tool call: delete <think> content
2. If GPT turn has <think> but no tool call: delete entire turn
3. If turn has no <think> but has tool call: add function call prefix
4. Finally remove all <think> and </think> tags
"""

import json
import os
import re
import sys
from typing import List, Dict, Any


def has_tool_use(content: str) -> bool:
    """Check if content contains tool calls"""
    tool_call_pattern = r'<tool_call>.*?</tool_call>'
    if re.search(tool_call_pattern, content, re.DOTALL):
        return True
    
    name_pattern = r'"name"\s*:\s*"[^"]+?"'
    arguments_pattern = r'"arguments"\s*:\s*'
    
    has_name = re.search(name_pattern, content)
    has_arguments = re.search(arguments_pattern, content)
    
    return has_name and has_arguments


def extract_function_name(content: str) -> str:
    """Extract function name from tool call"""
    tool_call_pattern = r'<tool_call>.*?"name"\s*:\s*"([^"]+)".*?</tool_call>'
    match = re.search(tool_call_pattern, content, re.DOTALL)
    if match:
        return match.group(1)
    
    name_pattern = r'"name"\s*:\s*"([^"]+)"'
    match = re.search(name_pattern, content)
    if match:
        return match.group(1)
    
    return ""


def remove_think_content(content: str) -> str:
    """Remove content between <think> tags"""
    pattern = r'<think>.*?</think>'
    return re.sub(pattern, '', content, flags=re.DOTALL)


def remove_think_tags(content: str) -> str:
    """Remove all <think> and </think> tags"""
    content = re.sub(r'<think>\n', '', content)
    content = re.sub(r'</think>', '', content)
    return content


def add_function_call_prefix(content: str) -> str:
    """Add function call prefix before tool call"""
    function_name = extract_function_name(content)
    if not function_name:
        return content
    
    prefix = f"I will call the function {function_name}.\n\n"
    tool_call_pattern = r'(<tool_call>)'
    if re.search(tool_call_pattern, content):
        return re.sub(tool_call_pattern, prefix + r'\1', content, count=1)
    
    return content

import json
import re
from typing import Dict, List, Any

def has_tool_use(content: str) -> bool:
    """检查内容是否包含工具调用（name和arguments）"""

    tool_call_pattern = r'<tool_call>.*?</tool_call>'
    if re.search(tool_call_pattern, content, re.DOTALL):
        return True
    

    name_pattern = r'"name"\s*:\s*"[^"]+?"'
    arguments_pattern = r'"arguments"\s*:\s*'
    
    has_name = re.search(name_pattern, content)
    has_arguments = re.search(arguments_pattern, content)
    
    return has_name and has_arguments

def process_conversation(conversation: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Process single conversation"""
    processed_turns = []
    
    for turn in conversation:
        if "value" not in turn:
            processed_turns.append(turn)
            continue
        
        content = turn["value"]
        role = turn.get("from", turn.get("role", ""))
        

        has_think = re.search(r'<think>.*?</think>', content, re.DOTALL)
        
        if has_think:
            if role.lower() in ["gpt", "assistant"] and not has_tool_use(content):
                continue
            if not has_tool_use(content):
                content = remove_think_content(content)
        else:
            if has_tool_use(content):
                content = add_function_call_prefix(content)
        
        content = remove_think_tags(content)
        turn["value"] = content
        processed_turns.append(turn)
    
    return processed_turns

def process_file(input_file: str, output_file: str = None):
    """Process JSON file"""
    if output_file is None:
        output_file = input_file.replace('.json', '_processed.json')
    
    print(f"Processing: {input_file}")
    
    with open(input_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    processed_data = []
    
    for i, item in enumerate(data):
        if "conversations" in item:
            if (i + 1) % 1000 == 0:
                print(f"Progress: {i + 1}/{len(data)}")
            processed_conversations = process_conversation(item["conversations"])
            
            if processed_conversations:
                item["conversations"] = processed_conversations
                processed_data.append(item)
        else:
            processed_data.append(item)
    
    print(f"Total: {len(data)}, Processed: {len(processed_data)}")
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(processed_data, f, ensure_ascii=False, indent=2)
    
    print(f"Saved to: {output_file}")

def main():
    if len(sys.argv) >= 3:
        input_file = sys.argv[1]
        output_file = sys.argv[2]
    elif len(sys.argv) == 2:
        print("Usage: python3 remove_think_tag.py <input_file> <output_file>")
        sys.exit(1)
    else:
        input_file = ""
        output_file = ""

    process_file(input_file, output_file)

if __name__ == "__main__":
    main()