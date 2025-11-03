#!/usr/bin/env python3
"""
Conversation Generation Module - AgentTuning Version
Core logic for handling GPT calls and Agent Trajectory generation
"""

import time
import json
from typing import Dict, List, Any, Optional
from openai import AzureOpenAI
from azure.identity import AzureCliCredential, get_bearer_token_provider

from .data_loader import DataLoader
from .gpt_logger import GPTLogger


class ConversationGenerator:
    """Agent Trajectory conversation generator"""
    
    def __init__(self, azure_config: Dict[str, Any], generation_settings: Dict[str, Any], 
                 data_loader: DataLoader, gpt_logger: GPTLogger):
        self.azure_config = azure_config
        self.generation_settings = generation_settings
        self.data_loader = data_loader
        self.gpt_logger = gpt_logger
        

        credential = AzureCliCredential()
        token_provider = get_bearer_token_provider(credential, "https://cognitiveservices.azure.com/.default")
        
        self.client = AzureOpenAI(
            azure_ad_token_provider=token_provider,
            azure_endpoint=azure_config.get('azure_endpoint', ''),
            api_version=azure_config.get('api_version', '2024-08-01-preview')
        )
        

        self.temperature = generation_settings.get('temperature', 1)
        self.max_tokens = generation_settings.get('max_tokens', 1000)
        self.retry_attempts = generation_settings.get('retry_attempts', 3)
        self.rate_limit_delay = generation_settings.get('rate_limit_delay', 0.1)
        

        self.deployment = azure_config.get('deployment', 'gpt-4o')
        self.timeout = azure_config.get('timeout', 30)
        

    
    def _get_tools_from_sample(self, sample: Dict[str, Any]) -> str:
        """Get tools configuration from sample"""
        tools_json = sample.get('tools', '[]')
        try:

            if isinstance(tools_json, str):
                tools = json.loads(tools_json)
            else:
                tools = tools_json
            

            tools_text = []
            for tool in tools:
                name = tool.get('name', '')
                description = tool.get('description', '')
                if name and description:
                    tools_text.append(f"- {name}: {description}")
            
            return "\n".join(tools_text)
        except Exception as e:
            print(f"Failed to parse tools: {e}")
            return ""
    
    def _extract_domain_from_sample(self, sample: Dict[str, Any]) -> str:
        """Extract domain info from sample (deprecated, APIGen doesn't need domain)"""

        return 'general'
    
    def generate_conversation_with_retry(self, sample: Dict[str, Any], attempt: int = 1) -> Dict[str, Any]:
        """Conversation generation with retry mechanism"""

        domain = self._extract_domain_from_sample(sample)
        sample_id = f"apigen_{domain}_{hash(str(sample.get('conversations', [])))}"
        
        for i in range(self.retry_attempts):
            try:
                result = self.generate_conversation_with_gpt(sample, attempt=i+1)
                if result and result.get('conversations'):
                    return result
                else:
                    print(f"Attempt {i+1} generation failed, no valid conversation content")
            except Exception as e:
                print(f"Attempt {i+1} generation error: {e}")

                self.gpt_logger.log_gpt_call(
                    prompt=f"Retry Attempt {i+1} failed",
                    response="",
                    sample_id=sample_id,
                    attempt=i+1,
                    error=str(e),
                    duration=0.0
                )
                if i < self.retry_attempts - 1:
                    time.sleep(self.rate_limit_delay * (i + 1))  
        

        return {"conversations": [], "tools": sample.get('tools', ''), "system": sample.get('system', ''),
                "based_on_sample": sample_id, 
                "sample_turns": len(sample.get('conversations', [])), "generated_turns": 0,
                "sample_question": self.data_loader.extract_question_from_sample(sample), "domain": domain}
    
    def generate_conversation_with_gpt(self, sample: Dict[str, Any], attempt: int = 1) -> Dict[str, Any]:
        """Generate new conversation using GPT, based on given APIGen sample"""
        sample_question = self.data_loader.extract_question_from_sample(sample)
        sample_conversation = self.data_loader.extract_conversation_from_sample(sample)
        sample_turns = len(sample_conversation)
        

        domain = self._extract_domain_from_sample(sample)
        

        sample_id = f"apigen_{domain}_{hash(str(sample_conversation))}"
        

        sample_text = self.data_loader.build_sample_text(sample)
        

        tools_config = self._get_tools_from_sample(sample)
        

        prompt = self.build_agent_trajectory_generation_prompt(sample_question, sample_text, tools_config)
        
        start_time = time.time()
        try:
            response = self.client.chat.completions.create(
                model=self.deployment,
                messages=[
                    {"role": "user", "content": prompt}
                ],
                temperature=self.temperature,
                max_completion_tokens=self.max_tokens,
                timeout=self.timeout
            )
            
            duration = time.time() - start_time
            response_content = response.choices[0].message.content
            

            if response_content is None:
                response_content = ""
            

            tokens_used = {}
            if hasattr(response, 'usage') and response.usage:
                tokens_used = {
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens
                }
            

            self.gpt_logger.log_gpt_call(
                prompt=prompt,
                response=response_content,
                sample_id=sample_id,
                attempt=attempt,
                duration=duration,
                tokens_used=tokens_used
            )
            
            result = self.parse_gpt_response(response_content)

            result['system'] = sample.get('system', '')
            result['tools'] = sample.get('tools', '')
            result['based_on_sample'] = sample_id
            result['sample_turns'] = sample_turns
            result['generated_turns'] = len(result.get('conversations', []))
            result['domain'] = domain
            

            result['sample_question'] = sample_question
            
            return result
            
        except Exception as e:
            duration = time.time() - start_time
            error_msg = str(e)
            

            self.gpt_logger.log_gpt_call(
                prompt=prompt,
                response="",
                sample_id=sample_id,
                attempt=attempt,
                error=error_msg,
                duration=duration
            )
            
            print(f"GPT call failed: {e}")
            return {"conversations": [], "tools": sample.get('tools', ''), "system": sample.get('system', ''),
                   "based_on_sample": sample_id, 
                   "sample_turns": sample_turns, "generated_turns": 0, 
                   "sample_question": sample_question, "domain": domain}
    
    def build_agent_trajectory_generation_prompt(self, sample_question: str, sample_text: str, available_tools: str = "") -> str:
        is_retail_sample = "Retail" in sample_text or "retail" in sample_text.lower()
        is_airline_sample = "airline" in sample_text.lower()
        
        if is_retail_sample:
            prompt = f"""You are an AI assistant that generates multi-turn conversation data for agent training. Your task is to create new agent trajectories based on existing examples.

## Example Trajectory:
{sample_text}

## Available Tools:
{available_tools}

CRITICAL FORMAT PRESERVATION REQUIREMENTS:
1. **STRICTLY PRESERVE ORIGINAL FORMAT**: You MUST maintain the EXACT format structure from the example trajectory (EXCEPTION: function_call turns may include <think> tags when reasoning is needed)
2. **NO SYSTEM PROMPT GENERATION**: Do NOT generate any SYSTEM messages - follow the system prompt from the original example and that will be preserved separately
3. **TOOL CONSTRAINT ADHERENCE**: You MUST STRICTLY use ONLY the tools listed in the "Available Tools" section above. DO NOT use any tools outside this specified allowed tool set. This is MANDATORY.
4. **FORMAT CONSISTENCY**: Maintain identical conversation structure, role naming conventions, and response patterns as shown in the example (EXCEPTION: function_call turns may include <think> tags when reasoning is added)
5. **TURN COUNT MATCHING**: Generate approximately the SAME NUMBER of conversation turns as the example trajectory - the generated conversation should have a comparable length and depth to the sample data

## CRITICAL RETAIL COMPLIANCE RULES:
1. **ALWAYS COMMUNICATE KEY NUMBERS**: State final total price, refund amount, tracking numbers, and price differences explicitly to user
2. **ORDER STATUS MATCHING**: Use pending tools for pending orders, delivered tools for delivered orders - NEVER mix them
3. **ID FORMAT CONSISTENCY**: When generating IDs (order IDs, item IDs, payment method IDs, user IDs), carefully observe the format and pattern used in the example trajectory and generat IDs that follow the same style. Avoid obvious fake patterns like "112233", "123456", etc. Use varied, realistic-looking combinations similar to those in the sample.

## FUNCTION_CALL TURN REQUIREMENTS:
1. **REASONING IN THINK TAGS**: When making function calls, add brief reasoning (1-3 sentences) inside `<think> </think>` tags ONLY in FUNCTION_CALL turns after you output 'FUNCTION_CALL:'
2. **SELECTIVE REASONING**: Not every function call needs reasoning. Only include it when it helps explain the complex decision-making process
3. **STRICT TURN CONSTRAINT**: Reasoning in `<think> </think>` tags should ONLY appear in FUNCTION_CALL turns, NEVER in HUMAN, GPT, OBSERRVATION or additional turns
4. **FORMAT REQUIREMENT**: If reasoning is included, the FUNCTION_CALL turn are allowed to add the thinking sentences instead of only JSON format. You should follow this format:
   ```
   FUNCTION_CALL:
   <think>
   Brief reasoning about why this function call is needed (1-3 sentences). Ended with: I will call the function <function_name>.
   </think>
   {{"name": "function_name", "arguments": {{...}}}}
   ```


## ABSOLUTE PROHIBITIONS:
- DO NOT use ANY tools that are not explicitly listed in the "Available Tools" section above
- DO NOT change the conversation format structure (human/gpt roles, value formatting, etc.) - EXCEPTION: function_call turns may include <think> tags when reasoning is needed
- DO NOT violate any fixed formatting elements, tool specifications, or requirements in system instructions from the example - EXCEPTION: function_call turns may include <think> tags when reasoning is added
- DO NOT generate significantly fewer or more turns than the example trajectory
- DO NOT invent or create new tools - use ONLY the provided tools

## Requirements:
1. Generate a completely NEW scenario/task that is different from the example but requires similar problem-solving patterns
2. Create a multi-turn conversation between Human and Assistant that demonstrates systematic problem-solving
3. The conversation should show the agent's reasoning process and step-by-step approach
4. **Start directly with a HUMAN message - do not include the SYSTEM content**
5. **CRITICAL: Ensure the generated conversation has approximately the same number of turns as the example trajectory**


## Agent Behavior Guidelines:
- Think step by step and explain reasoning
- Use ONLY the tools listed in the "Available Tools" section above - no exceptions
- Provide clear and helpful responses
- Maintain conversation flow and context
- Generate a conversation with comparable depth and turn count to the example
- Strictly adhere to the provided tool constraints without deviation

## Output Format:
Generate the conversation:
HUMAN: [user message content]
ASSISTANT: [assistant reply content]
HUMAN: [user message content]
ASSISTANT: [assistant reply content]
HUMAN: [user message content]
ASSISTANT: [assistant reply content]
...(until the task is finished and the conversation is complete)
"""
        elif is_airline_sample:
            prompt = f"""You are an AI assistant that generates multi-turn conversation data for agent training. Your task is to create new agent trajectories based on existing examples.

## Example Trajectory:
{sample_text}

## Available Tools:
{available_tools}

CRITICAL FORMAT PRESERVATION REQUIREMENTS - ABSOLUTE COMPLIANCE:
1. **STRICTLY PRESERVE ORIGINAL FORMAT**: You MUST maintain the EXACT format structure from the example trajectory (EXCEPTION: function_call turns may include <think> tags when reasoning is needed)
2. **NO SYSTEM PROMPT GENERATION**: Do NOT generate any SYSTEM messages - follow the system prompt from the original example and that will be preserved separately
3. **TOOL CONSTRAINT ADHERENCE**: You MUST STRICTLY use ONLY the tools listed in the "Available Tools" section above. DO NOT use any tools outside this specified allowed tool set. This is MANDATORY.
4. **FORMAT CONSISTENCY**: Maintain identical conversation structure, role naming conventions, and response patterns as shown in the example (EXCEPTION: function_call turns may include <think> tags when reasoning is added)
5. **TURN COUNT MATCHING**: Generate approximately the SAME NUMBER of conversation turns as the example trajectory - the generated conversation should have a comparable length and depth to the sample data

## AIRLINE POLICY COMPLIANCE REQUIREMENTS:
1. **CANCELLATION/REFUND POLICY VALIDATION**: 
   - ALWAYS check created_at timestamp - NO cancellation if >24 hours
   - Basic Economy tickets are NON-REFUNDABLE and NON-CHANGEABLE 
   - Verify insurance coverage BEFORE processing refunds
   - NO cancellation if ANY flight segment has already been flown
2. **CHANGE/UPGRADE POLICY VALIDATION**:
   - Basic Economy tickets CANNOT be changed or upgraded
   - NO simultaneous cabin change + flight change in single call
   - Destination changes are NOT allowed (only time/date changes)
   - Segment-level upgrades are prohibited
3. **ID FORMAT CONSISTENCY**: When generating IDs (reservation IDs, user IDs, flight numbers, payment method IDs), carefully observe the format and pattern used in the example trajectory and generate IDs that follow the same style. Avoid obvious fake patterns like "112233", "ABC123", etc. Use varied, realistic-looking combinations similar to those in the sample.

## FUNCTION_CALL TURN REQUIREMENTS:
1. **REASONING IN THINK TAGS**: When making function calls, add brief reasoning (1-3 sentences) inside `<think> </think>` tags ONLY in FUNCTION_CALL turns after you output 'FUNCTION_CALL:'
2. **SELECTIVE REASONING**: Not every function call needs reasoning. Only include it when it helps explain the complex decision-making process
3. **STRICT TURN CONSTRAINT**: Reasoning in `<think> </think>` tags should ONLY appear in FUNCTION_CALL turns, NEVER in HUMAN, GPT, OBSERRVATION or additional turns
4. **FORMAT REQUIREMENT**: If reasoning is included, the FUNCTION_CALL turn are allowed to add the thinking sentences instead of only JSON format. You should follow this format:
   ```
   FUNCTION_CALL:
   <think>
   Brief reasoning about why this function call is needed (1-3 sentences). Ended with: I will call the function <function_name>.
   </think>
   {{"name": "function_name", "arguments": {{...}}}}
   ```

## ABSOLUTE PROHIBITIONS:
- DO NOT use ANY tools that are not explicitly listed in the "Available Tools" section above
- DO NOT change the conversation format structure (human/gpt roles, value formatting, etc.) - EXCEPTION: function_call turns may include <think> tags when reasoning is needed
- DO NOT violate any fixed formatting elements, tool specifications, or requirements in system instructions from the example - EXCEPTION: function_call turns may include <think> tags when reasoning is added
- DO NOT generate significantly fewer or more turns than the example trajectory
- DO NOT invent or create new tools - use ONLY the provided tools
- DO NOT attempt cancellations/refunds beyond 24 hours or for Basic Economy
- DO NOT skip policy validation steps or tool call sequences

## Requirements:
1. Generate a completely NEW scenario/task that is different from the example but requires similar problem-solving patterns
2. Create a multi-turn conversation between Human and Assistant that demonstrates systematic problem-solving
3. The conversation should show the agent's reasoning process and step-by-step approach
4. **Start directly with a HUMAN message - do not include the SYSTEM content**
5. **CRITICAL: Ensure the generated conversation has approximately the same number of turns as the example trajectory**

## Agent Behavior Guidelines:
- Think step by step and explain reasoning
- Use ONLY the tools listed in the "Available Tools" section above - no exceptions
- Provide clear and helpful responses
- Maintain conversation flow and context
- Generate a conversation with comparable depth and turn count to the example
- Strictly adhere to the provided tool constraints without deviation

## Output Format:
Generate the conversation:
HUMAN: [user message content]
ASSISTANT: [assistant reply content]
HUMAN: [user message content]
ASSISTANT: [assistant reply content]
HUMAN: [user message content]
ASSISTANT: [assistant reply content]
...(until the task is finished and the conversation is complete)
"""
        return prompt
    

    
    def build_generation_prompt(self, sample_question: str, sample_text: str, sample: Dict[str, Any] = None) -> str:
        """Build generation prompt (using new agent trajectory method)"""
        if sample:
            tools_config = self._get_tools_from_sample(sample)
        else:
            tools_config = "" 
        return self.build_agent_trajectory_generation_prompt(sample_question, sample_text, tools_config)
    
    def parse_gpt_response(self, response_text: str) -> Dict[str, Any]:
        """Parse GPT response and convert to ShareGPT format"""

        
        lines = response_text.strip().split('\n')
        conversations = []
        
        current_role = None
        current_content = []
        
        for line in lines:
            line = line.strip()
            if line.startswith('HUMAN:') or line.startswith('H:'):
                if current_role and current_content:
                    conversations.append({
                        "from": current_role,
                        "value": '\n'.join(current_content).strip()
                    })
                current_role = "human"
                if line.startswith('HUMAN:'):
                    current_content = [line[6:].strip()]  
                elif line.startswith('H:'):
                    current_content = [line[2:].strip()] 
            elif line.startswith('ASSISTANT:') or line.startswith('A:'):
                if current_role and current_content:
                    conversations.append({
                        "from": current_role,
                        "value": '\n'.join(current_content).strip()
                    })
                current_role = "gpt" 
                if line.startswith('ASSISTANT:'):
                    current_content = [line[10:].strip()]  
                elif line.startswith('A:'):
                    current_content = [line[2:].strip()]  
            elif line.startswith('FUNCTION_CALL:'):
                if current_role and current_content:
                    conversations.append({
                        "from": current_role,
                        "value": '\n'.join(current_content).strip()
                    })
                current_role = "function_call"
                current_content = [line[14:].strip()]  
            elif line.startswith('OBSERVATION:'):
                if current_role and current_content:
                    conversations.append({
                        "from": current_role,
                        "value": '\n'.join(current_content).strip()
                    })
                current_role = "observation"
                current_content = [line[12:].strip()]  
            elif line and current_role:
                current_content.append(line)
        

        if current_role and current_content:
            conversations.append({
                "from": current_role,
                "value": '\n'.join(current_content).strip()
            })

        
        return {
            "conversations": conversations
        }
    
    def validate_generated_conversation(self, conv: Dict[str, Any]) -> bool:
        """Validate if generated conversation is valid"""
        if not conv or not conv.get('conversations'):
            return False
        
        conversations = conv['conversations']
        
        if len(conversations) == 0:
            return False
        
        for conversation in conversations:
            if not isinstance(conversation, dict):
                return False
            
            if 'from' not in conversation or 'value' not in conversation:
                return False
            
            if conversation['from'] not in ['human', 'gpt', 'function_call', 'observation']:
                return False
            
            if not conversation['value'] or not conversation['value'].strip():
                return False
        
        return True
    
    def get_generation_statistics(self, conversations: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Get generation statistics"""
        if not conversations:
            return {}
        
        total_turns = sum(len(conv.get('conversations', [])) for conv in conversations)
        sample_usage = {}
        domain_stats = {}
        
        for conv in conversations:
            sample_id = conv.get('based_on_sample', 'unknown')
            sample_turns = conv.get('sample_turns', 0)
            generated_turns = conv.get('generated_turns', 0)
            domain = conv.get('domain', 'unknown')
            
            if sample_id not in sample_usage:
                sample_usage[sample_id] = {
                    'count': 0,
                    'sample_turns': sample_turns,
                    'generated_turns': [],
                    'domain': domain
                }
            
            sample_usage[sample_id]['count'] += 1
            sample_usage[sample_id]['generated_turns'].append(generated_turns)
            
            if domain not in domain_stats:
                domain_stats[domain] = {
                    'count': 0,
                    'total_turns': 0,
                    'avg_turns': 0
                }
            domain_stats[domain]['count'] += 1
            domain_stats[domain]['total_turns'] += generated_turns
        
        for domain in domain_stats:
            if domain_stats[domain]['count'] > 0:
                domain_stats[domain]['avg_turns'] = domain_stats[domain]['total_turns'] / domain_stats[domain]['count']
        
        return {
            'total_conversations': len(conversations),
            'total_turns': total_turns,
            'avg_turns_per_conversation': total_turns / len(conversations) if conversations else 0,
            'sample_usage': sample_usage,
            'unique_samples_used': len(sample_usage),
            'domain_statistics': domain_stats
        }
    
    def post_process_conversation(self, conversation: Dict[str, Any]) -> Dict[str, Any]:
        """Post-process conversations - cleanup and normalization"""
        if not conversation or 'conversations' not in conversation:
            return conversation
        
        processed_conversations = []
        for conv in conversation['conversations']:
            if isinstance(conv, dict) and 'from' in conv and 'value' in conv:

                clean_value = conv['value'].strip()
                if clean_value:  
                    processed_conversations.append({
                        'from': conv['from'],
                        'value': clean_value
                    })
        

        conversation['conversations'] = processed_conversations
        conversation['generated_turns'] = len(processed_conversations)
        
        return conversation


def create_conversation_generator(azure_config: Dict[str, Any], generation_settings: Dict[str, Any], 
                                data_loader: DataLoader, gpt_logger: GPTLogger) -> ConversationGenerator:
    """Convenience function to create conversation generator"""
    return ConversationGenerator(azure_config, generation_settings, data_loader, gpt_logger)
