#!/usr/bin/env python3
"""
Data Post-processing Script - APIGen ShareGPT Format Version
Process generated conversation data, clean format, deduplicate, and validate
"""

import json
import os
import sys
import argparse
from typing import Dict, List, Any, Set
from pathlib import Path


class DataPostProcessor:
    """Data Post-processor"""
    
    def __init__(self):
        self.processed_conversations = []
        self.duplicate_count = 0
        self.invalid_count = 0
        self.seen_hashes = set()
    
    def hash_conversation(self, conversation: Dict[str, Any]) -> str:
        """Generate hash value of conversation for deduplication"""
        conversations = conversation.get('conversations', [])
        if not conversations:
            return ""
        
        content_parts = []
        for conv in conversations:
            if conv.get('from') == 'human':
                content_parts.append(f"H:{conv.get('value', '')}")
            elif conv.get('from') == 'gpt':
                content_parts.append(f"A:{conv.get('value', '')}")
        
        content_str = "|".join(content_parts)
        return str(hash(content_str))
    
    def validate_conversation(self, conversation: Dict[str, Any]) -> bool:
        """Validate if conversation format is correct"""
        if not isinstance(conversation, dict):
            return False
        
        conversations = conversation.get('conversations', [])
        if not isinstance(conversations, list) or len(conversations) == 0:
            return False
        
        for conv in conversations:
            if not isinstance(conv, dict):
                return False
            
            if 'from' not in conv or 'value' not in conv:
                return False
            
            if conv['from'] not in ['human', 'gpt', 'function_call', 'observation']:
                return False
            
            if not conv['value'] or not conv['value'].strip():
                return False
        
        if 'system' not in conversation or 'tools' not in conversation:
            return False
        
        return True
    
    def clean_conversation(self, conversation: Dict[str, Any]) -> Dict[str, Any]:
        """Clean conversation content"""
        cleaned = conversation.copy()
        
        if 'conversations' in cleaned:
            cleaned_conversations = []
            for conv in cleaned['conversations']:
                if isinstance(conv, dict) and 'from' in conv and 'value' in conv:
                    clean_conv = {
                        'from': conv['from'].strip(),
                        'value': conv['value'].strip()
                    }
                    if clean_conv['value']:  
                        cleaned_conversations.append(clean_conv)
            
            cleaned['conversations'] = cleaned_conversations
        
        if 'system' in cleaned:
            cleaned['system'] = cleaned['system'].strip()
        
        if 'tools' in cleaned and not isinstance(cleaned['tools'], str):
            try:
                cleaned['tools'] = json.dumps(cleaned['tools'])
            except:
                cleaned['tools'] = str(cleaned['tools'])
        
        return cleaned
    
    def process_file(self, input_file: str) -> List[Dict[str, Any]]:
        """Process input file"""
        print(f"📖 Processing file: {input_file}")
        
        try:
            with open(input_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            print(f"📊 Raw data: {len(data)} conversations")
            
            for i, conversation in enumerate(data):
                if i % 100 == 0:
                    print(f"   Progress: {i}/{len(data)}")
                
                cleaned_conversation = self.clean_conversation(conversation)
                
                if not self.validate_conversation(cleaned_conversation):
                    self.invalid_count += 1
                    continue
                
                conv_hash = self.hash_conversation(cleaned_conversation)
                if conv_hash in self.seen_hashes:
                    self.duplicate_count += 1
                    continue
                
                self.seen_hashes.add(conv_hash)
                self.processed_conversations.append(cleaned_conversation)
            
            print(f"✅ Processing complete")
            print(f"   Valid conversations: {len(self.processed_conversations)}")
            print(f"   Duplicate conversations: {self.duplicate_count}")
            print(f"   Invalid conversations: {self.invalid_count}")
            
            return self.processed_conversations
            
        except Exception as e:
            print(f"❌ Error processing file: {e}")
            return []
    
    def save_processed_data(self, output_file: str, conversations: List[Dict[str, Any]]) -> bool:
        """Save processed data"""
        try:
            output_dir = os.path.dirname(output_file)
            os.makedirs(output_dir, exist_ok=True)
            
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(conversations, f, ensure_ascii=False, indent=2)
            
            print(f"💾 Saved processed data to: {output_file}")
            return True
            
        except Exception as e:
            print(f"❌ Error saving file: {e}")
            return False
    
    def generate_statistics(self, conversations: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generate statistics"""
        if not conversations:
            return {}
        
        turn_counts = []
        domain_stats = {}
        
        for conv in conversations:
            conversations_list = conv.get('conversations', [])
            turn_counts.append(len(conversations_list))
            
            domain = conv.get('domain', 'unknown')
            if domain not in domain_stats:
                domain_stats[domain] = 0
            domain_stats[domain] += 1
        
        avg_turns = sum(turn_counts) / len(turn_counts) if turn_counts else 0
        
        return {
            'total_conversations': len(conversations),
            'avg_turns_per_conversation': avg_turns,
            'min_turns': min(turn_counts) if turn_counts else 0,
            'max_turns': max(turn_counts) if turn_counts else 0,
            'domain_distribution': domain_stats,
            'duplicate_removed': self.duplicate_count,
            'invalid_removed': self.invalid_count
        }


def main():
    parser = argparse.ArgumentParser(description='Data post-processing script')
    parser.add_argument('input_file', help='Input JSON file path')
    parser.add_argument('--output_dir', '-o', default='processed_output', help='Output directory')
    parser.add_argument('--stats', '-s', action='store_true', help='Generate statistics')
    
    args = parser.parse_args()
    
    if not os.path.exists(args.input_file):
        print(f"❌ Input file does not exist: {args.input_file}")
        sys.exit(1)
    
    processor = DataPostProcessor()
    
    conversations = processor.process_file(args.input_file)
    
    if not conversations:
        print("❌ No valid conversation data")
        sys.exit(1)
    

    input_path = Path(args.input_file)
    output_file = os.path.join(args.output_dir, f"{input_path.stem}_processed.json")
    

    if processor.save_processed_data(output_file, conversations):
        print(f"🎉 Data post-processing complete")
        

        if args.stats:
            stats = processor.generate_statistics(conversations)
            stats_file = os.path.join(args.output_dir, f"{input_path.stem}_stats.json")
            
            try:
                with open(stats_file, 'w', encoding='utf-8') as f:
                    json.dump(stats, f, ensure_ascii=False, indent=2)
                print(f"📊 Statistics saved to: {stats_file}")
            except Exception as e:
                print(f"⚠️ Failed to save statistics: {e}")
        
        print(f"📁 Output file: {output_file}")
    else:
        print("❌ Data post-processing failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
