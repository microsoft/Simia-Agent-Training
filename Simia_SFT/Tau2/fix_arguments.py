#!/usr/bin/env python3
"""
Data cleaning and repair script
1. Delete entire conversations containing '<tool_' or '\n[{'
2. Fix arguments format in function calls, converting arguments from string to dict
"""

import json
import sys
import os
import re
from typing import Dict, List, Any


def fix_arguments_format(func_call_str: str) -> tuple[bool, str, str]:
    """
    Fix arguments format errors.
    Supports two formats:
    1. Pure JSON: {"name": "xxx", "arguments": {...}}
    2. Think + JSON: <think>xxx</think>\n{"name": "xxx", "arguments": {...}}
    Returns (success, fixed_content, message)
    """
    try:
        # Check for <think> tag
        think_content = ""
        json_part = func_call_str.strip()
        
        if "<think>" in func_call_str and "</think>" in func_call_str:
            think_match = re.search(r'<think>(.*?)</think>\s*(.*)', func_call_str, re.DOTALL)
            if think_match:
                think_content = f"<think>{think_match.group(1)}</think>\n"
                json_part = think_match.group(2).strip()
        
        func_call = json.loads(json_part)
        if 'arguments' in func_call:
            arguments = func_call['arguments']
            
            if isinstance(arguments, str):
                try:
                    parsed_args = json.loads(arguments)
                    func_call['arguments'] = parsed_args
                    fixed_json = json.dumps(func_call, ensure_ascii=False)
                    fixed_str = think_content + fixed_json
                    return True, fixed_str, "Fixed: string to dict"
                except json.JSONDecodeError:
                    if arguments.strip():
                        cleaned_args = arguments.strip()
                        if cleaned_args.startswith('{') and cleaned_args.endswith('}'):
                            try:
                                fixed_args = cleaned_args.replace("'", '"')
                                parsed_args = json.loads(fixed_args)
                                func_call['arguments'] = parsed_args
                                fixed_json = json.dumps(func_call, ensure_ascii=False)
                                fixed_str = think_content + fixed_json
                                return True, fixed_str, "Fixed: quotes"
                            except:
                                pass
                        func_call['arguments'] = {}
                        fixed_json = json.dumps(func_call, ensure_ascii=False)
                        fixed_str = think_content + fixed_json
                        return True, fixed_str, "Warning: empty dict"
                    else:
                        func_call['arguments'] = {}
                        fixed_json = json.dumps(func_call, ensure_ascii=False)
                        fixed_str = think_content + fixed_json
                        return True, fixed_str, "Fixed: empty to dict"
            elif isinstance(arguments, dict):
                final_str = think_content + json.dumps(func_call, ensure_ascii=False) if think_content else func_call_str
                return True, final_str, "No fix needed"
            else:
                func_call['arguments'] = {}
                fixed_json = json.dumps(func_call, ensure_ascii=False)
                fixed_str = think_content + fixed_json
                return True, fixed_str, f"Fixed: {type(arguments).__name__} to dict"
        else:
            func_call['arguments'] = {}
            fixed_json = json.dumps(func_call, ensure_ascii=False)
            fixed_str = think_content + fixed_json
            return True, fixed_str, "Fixed: added arguments"
            
    except json.JSONDecodeError as e:
        return False, func_call_str, f"Invalid JSON format: {str(e)}"
    except Exception as e:
        return False, func_call_str, f"Fix error: {str(e)}"


def should_delete_conversation(conversation: List[Dict[str, Any]]) -> bool:
    """Check if conversation should be deleted (contains '<tool_' or '\n[{')"""
    for turn in conversation:
        value = turn.get('value', '')
        if '<tool_' in value or '\n[{' in value:
            return True
    return False


def process_conversation(conversation: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Process conversation and fix function call arguments"""
    fixed_conversation = []
    
    for turn in conversation:
        if turn.get('from') == 'function_call':
            func_call_str = turn.get('value', '')
            is_fixed, fixed_str, _ = fix_arguments_format(func_call_str)
            
            if is_fixed:
                fixed_turn = turn.copy()
                fixed_turn['value'] = fixed_str
                fixed_conversation.append(fixed_turn)
            else:
                fixed_conversation.append(turn)
        else:
            fixed_conversation.append(turn)
    
    return fixed_conversation


def process_data_file(data_file: str, output_file: str):
    """Process data file, delete bad conversations and fix arguments format"""
    print(f"Processing: {data_file}")
    
    with open(data_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    fixed_conversations = []
    deleted = 0
    
    for idx, item in enumerate(data):
        if 'conversations' in item:
            if should_delete_conversation(item['conversations']):
                deleted += 1
                continue
            
            fixed_conv = process_conversation(item['conversations'])
            fixed_item = item.copy()
            fixed_item['conversations'] = fixed_conv
            fixed_conversations.append(fixed_item)
        else:
            fixed_conversations.append(item)
        
        if (idx + 1) % 1000 == 0:
            print(f"Processed {idx + 1}/{len(data)}")
    
    print(f"Total: {len(data)}, Deleted: {deleted}, Kept: {len(fixed_conversations)}")
    return fixed_conversations


def main():
    if len(sys.argv) >= 3:
        data_file = sys.argv[1]
        output_file = sys.argv[2]
    elif len(sys.argv) == 2:
        print("Usage: python3 fix_arguments.py <input_file> <output_file>")
        sys.exit(1)
        data_file = ''
        output_file = ''

    print("Starting data cleaning and arguments fixing...")
    fixed_data = process_data_file(data_file, output_file)
    
    print(f"Saving to: {output_file}")
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(fixed_data, f, ensure_ascii=False, indent=2)
    
    print("Done!")


if __name__ == "__main__":
    main()
