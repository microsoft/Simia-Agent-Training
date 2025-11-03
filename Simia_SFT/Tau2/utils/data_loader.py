#!/usr/bin/env python3
"""
Data Loading Module - AgentTuning Version
Handle AgentTuning sample data loading and processing
"""

import json
import random
from typing import Dict, List, Any, Optional


class DataLoader:
    """AgentTuningData Loader"""
    
    def __init__(self, sample_data_path: str):
        self.sample_data_path = sample_data_path
        self.sample_conversations = self.load_sample_data()
    
    def load_sample_data(self) -> List[Dict[str, Any]]:
        """Load existing data as samples"""
        try:
            with open(self.sample_data_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                print(f"Successfully loaded  {len(data)}  samples conversations")
                return data
        except Exception as e:
            print(f"Failed to load sample data: {e}")
            return []
    
    def get_random_sample(self) -> Dict[str, Any]:
        """Randomly select a sample conversation"""
        if not self.sample_conversations:
            raise ValueError("No sample data available")
        return random.choice(self.sample_conversations)
    
    def extract_question_from_sample(self, sample: Dict[str, Any]) -> str:
        """Extract initial question from sample"""
        conversations = sample.get('conversations', [])
        if conversations and len(conversations) > 0:

            for conv in conversations:
                if conv.get('from') == 'human':
                    return conv.get('value', '')
        return "No question found"
    
    def extract_conversation_from_sample(self, sample: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract conversation content from sample"""

        return sample.get('conversations', [])
    
    def build_sample_text(self, sample: Dict[str, Any]) -> str:
        """Build sample text for reference, including system and conversations"""
        text_parts = []
        

        system_content = sample.get('system', '')
        if system_content:
            text_parts.append(f"SYSTEM: {system_content}")
        

        conversations = sample.get('conversations', [])
        for turn in conversations:
            role = turn.get('from', '')
            content = turn.get('value', '')
            if role == 'human':
                text_parts.append(f"HUMAN: {content}")
            elif role == 'gpt':
                text_parts.append(f"ASSISTANT: {content}")
            elif role == 'function_call':
                text_parts.append(f"FUNCTION_CALL: {content}")
            elif role == 'observation':
                text_parts.append(f"OBSERVATION: {content}")
        
        return '\n\n'.join(text_parts)
    
    def get_sample_statistics(self) -> Dict[str, Any]:
        """Get sample data statistics"""
        if not self.sample_conversations:
            return {}
        
        total_samples = len(self.sample_conversations)
        

        question_lengths = []
        conversation_lengths = []
        
        for sample in self.sample_conversations:
            question = self.extract_question_from_sample(sample)
            question_lengths.append(len(question))
            
            conversation = self.extract_conversation_from_sample(sample)
            conversation_lengths.append(len(conversation))
        
        avg_question_length = sum(question_lengths) / len(question_lengths) if question_lengths else 0
        avg_conversation_length = sum(conversation_lengths) / len(conversation_lengths) if conversation_lengths else 0
        
        return {
            'total_samples': total_samples,
            'avg_question_length': avg_question_length,
            'avg_conversation_turns': avg_conversation_length,
            'question_length_range': (min(question_lengths), max(question_lengths)) if question_lengths else (0, 0),
            'conversation_length_range': (min(conversation_lengths), max(conversation_lengths)) if conversation_lengths else (0, 0)
        }
    
    def show_sample_statistics(self) -> None:
        """Display sample data statistics"""
        stats = self.get_sample_statistics()
        
        if not stats:
            print("❌ No sample data available for statistics")
            return
        
        print("📊 Sample Data Statistics")
        print("=" * 50)
        print(f"📦 Total Samples: {stats['total_samples']}")
        print(f"📝 Average Question Length: {stats['avg_question_length']:.1f} characters")
        print(f"💬 Average Conversation Turns: {stats['avg_conversation_turns']:.1f}")
        print(f"📏 Question Length Range: {stats['question_length_range'][0]} - {stats['question_length_range'][1]} characters")
        print(f"🔄 Conversation Length Range: {stats['conversation_length_range'][0]} - {stats['conversation_length_range'][1]} turns")
        print("=" * 50)
    
    def validate_sample_data(self) -> bool:
        """Validate sample data integrity"""
        if not self.sample_conversations:
            print("❌ No sample data")
            return False
        
        invalid_samples = 0
        for i, sample in enumerate(self.sample_conversations):
            try:
                if 'conversations' not in sample:
                    print(f"❌ Sample  {i} missing conversations field")
                    invalid_samples += 1
                    continue
                
                conversations = sample['conversations']
                if not conversations:
                    print(f"❌ Sample  {i} conversations is empty")
                    invalid_samples += 1
                    continue
                
                for j, conv in enumerate(conversations):
                    if 'from' not in conv or 'value' not in conv:
                        print(f"❌ Sample  {i}  conversation turn {j} missing required fields (from/value)")
                        invalid_samples += 1
                        break
                
                if 'tools' not in sample:
                    print(f"⚠️ Sample  {i} missing tools field")
                if 'system' not in sample:
                    print(f"⚠️ Sample  {i} missing system field")
                        
            except Exception as e:
                print(f"❌ Validating sample  {i} error occurred: {e}")
                invalid_samples += 1
        
        if invalid_samples > 0:
            print(f"❌ Found {invalid_samples} invalid samples ")
            return False
        else:
            print(f"✅ All {len(self.sample_conversations)}  samples validated successfully")
            return True


def create_data_loader(sample_data_path: str) -> DataLoader:
    """Convenience function to create data loader"""
    return DataLoader(sample_data_path)
