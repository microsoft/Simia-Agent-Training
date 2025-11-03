#!/usr/bin/env python3

import json
import os
import re
from typing import Dict, List, Any, Optional
import logging

# Setup logging
logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

class MultiDomainToolUseValidator:
    def __init__(self, tools_spec_path: str):
        """Initialize multi-domain validator
        
        Args:
            tools_spec_path: Path to tools specification file
        """
        self.tools_spec = self._load_tools_spec(tools_spec_path)
        
        self.retail_config = self.tools_spec.get("tools_config_2", {})
        self.airline_config = self.tools_spec.get("tools_config_3", {})
        
        self.retail_tools = self._build_tools_dict(self.retail_config)
        self.airline_tools = self._build_tools_dict(self.airline_config)
        
        self.discarded_conversations = 0
        
    def _load_tools_spec(self, path: str) -> Dict:
        """Load tools specification file"""
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load tools spec file: {e}")
            raise
            
    def _build_tools_dict(self, tools_config: Dict) -> Dict[str, Dict]:
        """Build mapping from tool name to tool specification"""
        tools_dict = {}
        for tool in tools_config.get("tools", []):
            if tool.get("type") == "function":
                func_name = tool["function"]["name"]
                tools_dict[func_name] = tool["function"]
        return tools_dict
        
    def _is_retail_domain(self, conversation: Dict) -> bool:
        """Check if conversation is from retail domain"""
        system_content = conversation.get("system", "").lower()
        if "retail" in system_content:
            return True
        for msg in conversation.get("conversations", []):
            if msg.get("from") == "system":
                system_content = msg.get("value", "").lower()
                if "retail" in system_content:
                    return True
        return False
        
    def _is_airline_domain(self, conversation: Dict) -> bool:
        """Check if conversation is from airline domain"""
        system_content = conversation.get("system", "").lower()
        if "airline" in system_content:
            return True
        for msg in conversation.get("conversations", []):
            if msg.get("from") == "system":
                system_content = msg.get("value", "").lower()
                if "airline" in system_content:
                    return True
        return False
        
    def _contains_think(self, conversation: Dict) -> bool:
        """Check if conversation contains think tool calls (excluding <think> tags for reasoning)"""
        for msg in conversation.get("conversations", []):
            if msg.get("from") == "function_call":
                content = msg.get("value", "")
                if isinstance(content, str):
                    json_part = content.strip()
                    if "<think>" in content and "</think>" in content:
                        think_match = re.search(r'<think>(.*?)</think>\s*(.*)', content, re.DOTALL)
                        if think_match:
                            json_part = think_match.group(2).strip()
                    
                    try:
                        call_data = json.loads(json_part)
                        if call_data.get("name") == "think":
                            return True
                    except json.JSONDecodeError:
                        if '"name": "think"' in json_part or '"name":"think"' in json_part:
                            return True
            
            content = msg.get("value", "")
            if isinstance(content, str):
                tool_call_pattern = r'<tool_call>\s*({.*?})\s*</tool_call>'
                matches = re.findall(tool_call_pattern, content, re.DOTALL)
                
                for match in matches:
                    try:
                        tool_call_data = json.loads(match)
                        if tool_call_data.get("name") == "think":
                            return True
                    except json.JSONDecodeError:
                        if '"name"' in match and '"think"' in match:
                            if '"name": "think"' in match or '"name":"think"' in match:
                                return True
                        continue
                    except Exception:
                        continue
        return False
        
    def validate_and_fix_conversation(self, conversation: Dict) -> Optional[Dict]:
        """Validate and fix tool usage in conversation
        
        Strict mode: any tool specification violation will discard the entire data
        """
        if self._contains_think(conversation):
            self.discarded_conversations += 1
            return None
            
        is_retail = self._is_retail_domain(conversation)
        is_airline = self._is_airline_domain(conversation)
        
        if is_retail:
            result = self._validate_with_tools(conversation, self.retail_tools, "retail")
            return result
        elif is_airline:
            result = self._validate_with_tools(conversation, self.airline_tools, "airline")
            return result
        else:
            return conversation
            
    def _validate_with_tools(self, conversation: Dict, tools_dict: Dict, domain: str) -> Optional[Dict]:
        """Validate conversation with specified domain tools"""
        try:
            fixed_conversations = []
            for message in conversation.get("conversations", []):
                fixed_message = self._fix_message_tool_calls(message, tools_dict, domain)
                if fixed_message is None:
                    self.discarded_conversations += 1
                    return None
                fixed_conversations.append(fixed_message)
                
            fixed_conversation = conversation.copy()
            fixed_conversation["conversations"] = fixed_conversations
            return fixed_conversation
            
        except Exception as e:
            logger.error(f"Error validating {domain} conversation: {e}")
            return None
            
    def _fix_message_tool_calls(self, message: Dict, tools_dict: Dict, domain: str) -> Optional[Dict]:
        """Fix tool calls in message, supporting two formats:
        1. <tool_call> format in assistant/gpt messages
        2. function_call format as separate message
        """
        if message.get("from") == "function_call":
            return self._fix_function_call_message(message, tools_dict, domain)
            
        if message.get("from") not in ["assistant", "gpt"]:
            return message
            
        content = message.get("value", "")
        if not isinstance(content, str) or "<tool_call>" not in content:
            return message
            
        tool_call_pattern = r'<tool_call>\s*({.*?})\s*</tool_call>'
        matches = list(re.finditer(tool_call_pattern, content, re.DOTALL))
        
        if not matches:
            return message
            
        fixed_content = content
        for match in reversed(matches):
            try:
                tool_call_data = json.loads(match.group(1))
                formatted_call = {
                    "function": {
                        "name": tool_call_data["name"],
                        "arguments": tool_call_data["arguments"]
                    }
                }
                
                fixed_call = self._validate_and_fix_tool_call(formatted_call, tools_dict, domain)
                if fixed_call is None:
                    return None
                    
                new_tool_call_json = json.dumps({
                    "name": fixed_call["function"]["name"],
                    "arguments": fixed_call["function"]["arguments"]
                })
                
                new_tool_call_str = f"<tool_call>\n{new_tool_call_json}\n</tool_call>"
                fixed_content = fixed_content[:match.start()] + new_tool_call_str + fixed_content[match.end():]
                
            except (json.JSONDecodeError, Exception):
                return None
                
        fixed_message = message.copy()
        fixed_message["value"] = fixed_content
        return fixed_message
        
    def _fix_function_call_message(self, message: Dict, tools_dict: Dict, domain: str) -> Optional[Dict]:
        """Fix function_call format message (APIGen format)
        
        Supports two formats:
        1. Pure JSON: {"name": "xxx", "arguments": {...}}
        2. Think+JSON: <think>xxx</think>\n{"name": "xxx", "arguments": {...}}
        """
        try:
            content = message.get("value", "")
            if not isinstance(content, str):
                return None
            
            think_content = ""
            json_part = content.strip()
            
            if "<think>" in content and "</think>" in content:
                think_match = re.search(r'<think>(.*?)</think>\s*(.*)', content, re.DOTALL)
                if think_match:
                    think_content = f"<think>{think_match.group(1)}</think>\n"
                    json_part = think_match.group(2).strip()
                
            tool_call_data = json.loads(json_part)
            
            formatted_call = {
                "function": {
                    "name": tool_call_data.get("name"),
                    "arguments": tool_call_data.get("arguments", {})
                }
            }
            
            fixed_call = self._validate_and_fix_tool_call(formatted_call, tools_dict, domain)
            if fixed_call is None:
                return None
                
            new_json = json.dumps({
                "name": fixed_call["function"]["name"],
                "arguments": fixed_call["function"]["arguments"]
            })
            
            new_content = think_content + new_json
            
            fixed_message = message.copy()
            fixed_message["value"] = new_content
            return fixed_message
            
        except (json.JSONDecodeError, Exception):
            return None
        
    def _validate_and_fix_tool_call(self, tool_call: Dict, tools_dict: Dict, domain: str) -> Optional[Dict]:
        """Validate and fix single tool call with strict validation"""
        try:
            function_info = tool_call.get("function", {})
            func_name = function_info.get("name")
            arguments = function_info.get("arguments", {})
            
            if not func_name or func_name not in tools_dict:
                return None
            
            if isinstance(arguments, str):
                try:
                    arguments = json.loads(arguments)
                except json.JSONDecodeError:
                    return None
            
            if not isinstance(arguments, dict):
                return None
                
            tool_spec = tools_dict[func_name]
            parameters_spec = tool_spec.get("parameters", {})
            properties = parameters_spec.get("properties", {})
            required_params = parameters_spec.get("required", [])
            
            for param in required_params:
                if param not in arguments:
                    return None
                    
            for param_name in arguments.keys():
                if param_name not in properties:
                    return None
            
            fixed_arguments = {}
            for param_name, param_value in arguments.items():
                param_spec = properties[param_name]
                expected_type = param_spec.get("type")
                
                if not self._validate_parameter_type(param_value, expected_type, param_spec):
                    return None
                    
                if domain == "retail":
                    fixed_value = self._fix_parameter_format_retail(param_name, param_value, func_name)
                    if not self._validate_parameter_format_retail(param_name, fixed_value, func_name):
                        return None
                else:
                    fixed_value = param_value
                    
                fixed_arguments[param_name] = fixed_value
                    
            return {
                "function": {
                    "name": func_name,
                    "arguments": fixed_arguments
                }
            }
            
        except Exception:
            return None
            
    def _fix_parameter_format_retail(self, param_name: str, param_value: Any, func_name: str) -> Any:
        """Fix retail domain parameter format"""
        if not isinstance(param_value, str):
            return param_value
            
        if param_name == "order_id":
            if not param_value.startswith("#"):
                return f"#{param_value}"
                
        return param_value
        
    def _validate_parameter_format_retail(self, param_name: str, param_value: Any, func_name: str) -> bool:
        """Validate retail domain parameter format"""
        if not isinstance(param_value, str):
            return True
            
        if param_name == "order_id":
            return param_value.startswith("#")
        elif param_name == "email":
            return "@" in param_value
        elif param_name == "payment_method_id":
            return (param_value.startswith("gift_card_") or 
                   param_value.startswith("credit_card_") or
                   param_value.startswith("paypal_"))
                
        return True
        
    def _validate_parameter_type(self, value: Any, expected_type: str, param_spec: Dict) -> bool:
        """Validate parameter type"""
        if expected_type == "string":
            return isinstance(value, str)
        elif expected_type == "array":
            if not isinstance(value, list):
                return False
            items_spec = param_spec.get("items", {})
            items_type = items_spec.get("type")
            if items_type:
                return all(self._validate_parameter_type(item, items_type, {}) for item in value)
            return True
        elif expected_type == "object":
            return isinstance(value, dict)
        elif expected_type == "number":
            return isinstance(value, (int, float))
        elif expected_type == "integer":
            return isinstance(value, int)
        elif expected_type == "boolean":
            return isinstance(value, bool)
        else:
            return True
            
    def process_dataset(self, input_path: str, output_path: str) -> None:
        """Process dataset"""
        print(f"Processing: {input_path}")
        
        try:
            with open(input_path, 'r', encoding='utf-8') as f:
                dataset = json.load(f)
                
            original_count = len(dataset)
            
            valid_conversations = []
            self.discarded_conversations = 0
            
            for conversation in dataset:
                fixed_conversation = self.validate_and_fix_conversation(conversation)
                if fixed_conversation is not None:
                    valid_conversations.append(fixed_conversation)
                    
            print(f"Original: {original_count}, Valid: {len(valid_conversations)}, Discarded: {self.discarded_conversations}")
            
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(valid_conversations, f, ensure_ascii=False, indent=2)
                
            print(f"Saved to: {output_path}")
            
        except Exception as e:
            logger.error(f"Error processing dataset: {e}")
            raise


class ToolUseValidator:
    def __init__(self, tools_spec_path: str, domain: str = "retail"):
        """Initialize validator
        
        Args:
            tools_spec_path: Path to tools specification file
            domain: Domain to process, "retail" or "airline"
        """
        self.domain = domain
        self.tools_spec = self._load_tools_spec(tools_spec_path)
        
        if domain == "retail":
            self.tools_config = self.tools_spec.get("tools_config_2", {})
        elif domain == "airline":
            self.tools_config = self.tools_spec.get("tools_config_3", {})
        else:
            raise ValueError(f"Unsupported domain: {domain}")
            
        self.tools_dict = self._build_tools_dict()
        self.discarded_conversations = 0
        
    def _load_tools_spec(self, path: str) -> Dict:
        """Load tools specification file"""
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load tools spec: {e}")
            raise
            
    def _build_tools_dict(self) -> Dict[str, Dict]:
        """Build mapping from tool name to tool specification"""
        tools_dict = {}
        for tool in self.tools_config.get("tools", []):
            if tool.get("type") == "function":
                func_name = tool["function"]["name"]
                tools_dict[func_name] = tool["function"]
        return tools_dict
        
    def _is_target_domain(self, conversation: Dict) -> bool:
        """Check if conversation is from target domain"""
        system_content = conversation.get("system", "").lower()
        if self.domain in system_content:
            return True
            
        for msg in conversation.get("conversations", []):
            if msg.get("from") == "system":
                system_content = msg.get("value", "").lower()
                if self.domain in system_content:
                    return True
        return False
        
    def _contains_think(self, conversation: Dict) -> bool:
        """Check if conversation contains think tool calls"""
        for msg in conversation.get("conversations", []):
            if msg.get("from") == "function_call":
                content = msg.get("value", "")
                if isinstance(content, str):
                    try:
                        call_data = json.loads(content)
                        if call_data.get("name") == "think":
                            return True
                    except json.JSONDecodeError:
                        if '"name": "think"' in content or '"name":"think"' in content:
                            return True
            
            content = msg.get("value", "")
            if isinstance(content, str):
                if 'tool_call' in content and 'think' in content:
                    if '"name": "think"' in content or '"name":"think"' in content:
                        return True
                    if '\\"name\\": \\"think\\"' in content or '\\"name\\":\\"think\\"' in content:
                        return True
                
                tool_call_pattern = r'<tool_call>\s*({.*?})\s*</tool_call>'
                matches = re.findall(tool_call_pattern, content, re.DOTALL)
                
                for match in matches:
                    try:
                        tool_call_data = json.loads(match)
                        if tool_call_data.get("name") == "think":
                            return True
                    except json.JSONDecodeError:
                        if '"name"' in match and 'think' in match:
                            return True
                        continue
                    except Exception:
                        continue
        return False
        
    def _fix_parameter_format(self, param_name: str, param_value: Any, func_name: str) -> Any:
        """Try to fix parameter format"""
        if not isinstance(param_value, str):
            return param_value
            
        if self.domain == "retail":
            if param_name == "order_id":
                if not param_value.startswith("#"):
                    return f"#{param_value}"
                    
            if param_name == "payment_method_id":
                if param_value.startswith("paypal_"):
                    return param_value
                elif param_value.startswith("credit_card_"):
                    return param_value
                elif param_value.startswith("gift_card_"):
                    return param_value
                elif param_value.startswith("cc_") or param_value.startswith("card_") or param_value.startswith("credit_"):
                    card_id = param_value.split("_", 1)[-1]
                    return f"credit_card_{card_id}"
                elif param_value.startswith("giftcard_") or param_value.startswith("gc_"):
                    card_id = param_value.split("_", 1)[-1]
                    return f"gift_card_{card_id}"
                elif param_value.startswith("gift_") and param_value != "gift_card":
                    card_id = param_value.split("_", 1)[-1]
                    return f"gift_card_{card_id}"
                elif param_value == "gift_card":
                    return param_value
                elif param_value.startswith("visa_"):
                    card_id = param_value.split("_", 1)[-1]
                    return f"credit_card_{card_id}"
                elif param_value.startswith("creditcard_"):
                    card_id = param_value.split("_", 1)[-1]
                    return f"credit_card_{card_id}"
                
        return param_value
        
    def _validate_parameter_format(self, param_name: str, param_value: Any, func_name: str) -> bool:
        """Validate parameter format (after fixing)"""
        if not isinstance(param_value, str):
            return True
            
        if self.domain == "retail":
            if param_name == "order_id":
                return param_value.startswith("#")
            if param_name == "email":
                return "@" in param_value
            if param_name == "payment_method_id":
                return (param_value.startswith("gift_card_") or 
                       param_value.startswith("credit_card_") or
                       param_value.startswith("paypal_"))
                
        return True
        
    def _validate_parameter_type(self, value: Any, expected_type: str, param_spec: Dict) -> bool:
        """Validate parameter type"""
        if expected_type == "string":
            return isinstance(value, str)
        elif expected_type == "array":
            if not isinstance(value, list):
                return False
            items_spec = param_spec.get("items", {})
            items_type = items_spec.get("type")
            if items_type:
                return all(self._validate_parameter_type(item, items_type, {}) for item in value)
            return True
        elif expected_type == "object":
            return isinstance(value, dict)
        elif expected_type == "number":
            return isinstance(value, (int, float))
        elif expected_type == "integer":
            return isinstance(value, int)
        elif expected_type == "boolean":
            return isinstance(value, bool)
        else:
            return True
            
    def _validate_and_fix_tool_call(self, tool_call: Dict) -> Optional[Dict]:
        """Validate and fix single tool call with strict validation"""
        try:
            function_info = tool_call.get("function", {})
            func_name = function_info.get("name")
            arguments = function_info.get("arguments", {})
            
            if not func_name or func_name not in self.tools_dict:
                return None
            
            if isinstance(arguments, str):
                try:
                    arguments = json.loads(arguments)
                except json.JSONDecodeError:
                    return None
            
            if not isinstance(arguments, dict):
                return None
                
            tool_spec = self.tools_dict[func_name]
            parameters_spec = tool_spec.get("parameters", {})
            properties = parameters_spec.get("properties", {})
            required_params = parameters_spec.get("required", [])
            
            for param in required_params:
                if param not in arguments:
                    return None
                    
            for param_name in arguments.keys():
                if param_name not in properties:
                    return None
            
            fixed_arguments = {}
            for param_name, param_value in arguments.items():
                param_spec = properties[param_name]
                expected_type = param_spec.get("type")
                
                if not self._validate_parameter_type(param_value, expected_type, param_spec):
                    return None
                    
                if self.domain == "retail":
                    fixed_value = self._fix_parameter_format(param_name, param_value, func_name)
                    if not self._validate_parameter_format(param_name, fixed_value, func_name):
                        return None
                else:
                    fixed_value = param_value
                    
                fixed_arguments[param_name] = fixed_value
                    
            return {
                "function": {
                    "name": func_name,
                    "arguments": fixed_arguments
                }
            }
            
        except Exception:
            return None
            
    def _fix_message_tool_calls(self, message: Dict) -> Optional[Dict]:
        """Fix tool calls in message"""
        if message.get("from") == "function_call":
            return self._fix_function_call_message_single(message)
            
        if message.get("from") not in ["assistant", "gpt"]:
            return message
            
        content = message.get("value", "")
        if not isinstance(content, str) or "<tool_call>" not in content:
            return message
            
        tool_call_pattern = r'<tool_call>\s*({.*?})\s*</tool_call>'
        matches = list(re.finditer(tool_call_pattern, content, re.DOTALL))
        
        if not matches:
            return message
            
        fixed_content = content
        for match in reversed(matches):
            try:
                tool_call_data = json.loads(match.group(1))
                formatted_call = {
                    "function": {
                        "name": tool_call_data["name"],
                        "arguments": tool_call_data["arguments"]
                    }
                }
                
                fixed_call = self._validate_and_fix_tool_call(formatted_call)
                if fixed_call is None:
                    return None
                    
                new_tool_call_json = json.dumps({
                    "name": fixed_call["function"]["name"],
                    "arguments": fixed_call["function"]["arguments"]
                })
                
                new_tool_call_str = f"<tool_call>\n{new_tool_call_json}\n</tool_call>"
                fixed_content = fixed_content[:match.start()] + new_tool_call_str + fixed_content[match.end():]
                
            except (json.JSONDecodeError, Exception):
                return None
                
        fixed_message = message.copy()
        fixed_message["value"] = fixed_content
        return fixed_message
        
    def _fix_function_call_message_single(self, message: Dict) -> Optional[Dict]:
        """Fix function_call format message"""
        try:
            content = message.get("value", "")
            if not isinstance(content, str):
                return None
                
            tool_call_data = json.loads(content)
            
            formatted_call = {
                "function": {
                    "name": tool_call_data.get("name"),
                    "arguments": tool_call_data.get("arguments", {})
                }
            }
            
            fixed_call = self._validate_and_fix_tool_call(formatted_call)
            if fixed_call is None:
                return None
                
            new_content = json.dumps({
                "name": fixed_call["function"]["name"],
                "arguments": fixed_call["function"]["arguments"]
            })
            
            fixed_message = message.copy()
            fixed_message["value"] = new_content
            return fixed_message
            
        except (json.JSONDecodeError, Exception):
            return None
        
    def validate_and_fix_conversation(self, conversation: Dict) -> Optional[Dict]:
        """Validate and fix tool usage in conversation"""
        if self._contains_think(conversation):
            self.discarded_conversations += 1
            return None
            
        if not self._is_target_domain(conversation):
            return conversation
            
        try:
            fixed_conversations = []
            for message in conversation.get("conversations", []):
                fixed_message = self._fix_message_tool_calls(message)
                if fixed_message is None:
                    self.discarded_conversations += 1
                    return None
                fixed_conversations.append(fixed_message)
                
            fixed_conversation = conversation.copy()
            fixed_conversation["conversations"] = fixed_conversations
            return fixed_conversation
            
        except Exception:
            return None
            
    def process_dataset(self, input_path: str, output_path: str) -> None:
        """Process dataset"""
        print(f"Processing: {input_path}")
        
        try:
            with open(input_path, 'r', encoding='utf-8') as f:
                dataset = json.load(f)
                
            original_count = len(dataset)
            
            valid_conversations = []
            self.discarded_conversations = 0
            
            for conversation in dataset:
                fixed_conversation = self.validate_and_fix_conversation(conversation)
                if fixed_conversation is not None:
                    valid_conversations.append(fixed_conversation)
                    
            print(f"Original: {original_count}, Valid: {len(valid_conversations)}, Discarded: {self.discarded_conversations}")
            
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(valid_conversations, f, ensure_ascii=False, indent=2)
                
            print(f"Saved to: {output_path}")
            
        except Exception as e:
            logger.error(f"Error processing dataset: {e}")
            raise

def main():
    """Main function"""
    import sys
    
    if len(sys.argv) >= 4:
        input_file = sys.argv[1]
        output_path = sys.argv[2]
        tools_spec_path = sys.argv[3]
    elif len(sys.argv) >= 3:
        print("Usage: python3 tool_correct.py <input_file> <output_file> <tools_spec_path>")
        print("Or: python3 tool_correct.py <input_file> <output_file> (use default tools_spec)")
        input_file = sys.argv[1]
        output_path = sys.argv[2]
        tools_spec_path = "Simia_SFT/Tau2/tools_seed.json"
    elif len(sys.argv) == 2:
        print("Usage: python3 tool_correct.py <input_file> <output_file> [tools_spec_path]")
        sys.exit(1)
    else:
        tools_spec_path = "Simia_SFT/Tau2/tools_seed.json"
        input_file = ""

        input_dir = os.path.dirname(input_file)
        input_filename = os.path.basename(input_file)
        name_without_ext = os.path.splitext(input_filename)[0]
        output_filename = f"{name_without_ext}_toolv6.json"
        output_path = os.path.join(input_dir, output_filename)
    
    if not os.path.exists(tools_spec_path):
        print(f"Tools spec file not found: {tools_spec_path}")
        return
        
    if not os.path.exists(input_file):
        print(f"Input file not found: {input_file}")
        return
    
    try:
        validator = MultiDomainToolUseValidator(tools_spec_path)
        validator.process_dataset(input_file, output_path)
        print("Processing completed!")
        
    except Exception as e:
        print(f"Error: {e}")
        

if __name__ == "__main__":
    main()
