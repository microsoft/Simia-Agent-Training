#!/usr/bin/env python3
"""
Progress Management Module
Handle saving, loading, validation and management of generation progress
"""

import json
import os
import shutil
from typing import Dict, List, Any, Optional
from datetime import datetime


class ProgressManager:
    """Progress Manager"""
    
    def __init__(self, output_path: str, config_hash: str):
        self.output_path = output_path
        self.config_hash = config_hash
        self.progress_file = self.output_path.replace('.json', '_progress.json')
        self.state_file = self.progress_file.replace('.json', '_state.json')
    
    def save_progress(self, conversations: List[Dict[str, Any]], target_count: int, 
                      save_enabled: bool = True) -> None:
        """Save progress to file"""
        if not save_enabled:
            return
            
        try:
            with open(self.progress_file, 'w', encoding='utf-8') as f:
                json.dump(conversations, f, ensure_ascii=False, indent=2)
            
            state_data = {
                'timestamp': datetime.now().isoformat(),
                'total_conversations': len(conversations),
                'target_count': target_count,
                'config_hash': self.config_hash,
                'last_successful_index': len(conversations) - 1 if conversations else -1,
                'failed_attempts': 0,
                'generation_stats': self._get_generation_stats(conversations)
            }
            
            with open(self.state_file, 'w', encoding='utf-8') as f:
                json.dump(state_data, f, ensure_ascii=False, indent=2)
            
            print(f"💾 Progress saved: {len(conversations)} conversations")
            
        except Exception as e:
            print(f"❌ Failed to save progress: {e}")
    
    def load_progress(self) -> List[Dict[str, Any]]:
        """Load progress from file"""
        if not os.path.exists(self.progress_file):
            return []
            
        try:
            with open(self.progress_file, 'r', encoding='utf-8') as f:
                conversations = json.load(f)

            if not self._validate_conversations(conversations):
                print("⚠️  Data integrity issue detected, will create backup and restart")
                self._backup_corrupted_data()
                return []
            
            if os.path.exists(self.state_file):
                try:
                    with open(self.state_file, 'r', encoding='utf-8') as f:
                        state_data = json.load(f)

                    if state_data.get('config_hash') != self.config_hash:
                        print("⚠️  Configuration file has changed, progress file may be incompatible")
                        choice = input("Do you want to continue using existing progress? (y/n): ")
                        if choice.lower() != 'y':
                            return []
                    
                    print(f"📂 Progress loaded: {len(conversations)} conversations")
                    print(f"📅 Last saved: {state_data.get('timestamp', 'unknown')}")
                    print(f"🎯 Target count: {state_data.get('target_count', 'unknown')}")
                    
                except Exception as e:
                    print(f"⚠️  Failed to load state file: {e}")
            
            return conversations
            
        except Exception as e:
            print(f"❌ Failed to load progress file: {e}")
            self._backup_corrupted_data()
            return []
    
    def _validate_conversations(self, conversations: List[Dict[str, Any]]) -> bool:
        """Validate conversation data integrity"""
        if not conversations:
            return True
        
        for i, conv in enumerate(conversations):

            if not isinstance(conv, dict):
                print(f"⚠️  Conversation {i} is not a dictionary")
                return False
            
            if 'conversations' not in conv:
                print(f"⚠️  Conversation {i} missing conversations field")
                return False
            
            if not isinstance(conv['conversations'], list):
                print(f"⚠️  Conversation {i} conversations field is not a list")
                return False
            

            for j, turn in enumerate(conv['conversations']):
                if not isinstance(turn, dict):
                    print(f"⚠️  Conversation {i} turn {j} is not a dictionary")
                    return False
                
                if 'from' not in turn or 'value' not in turn:
                    print(f"⚠️  Conversation {i} turn {j} missing required fields")
                    return False
                
                if turn['from'] not in ['system', 'user', 'assistant', 'gpt', 'human', 'function_call', 'observation']:
                    print(f"⚠️  Conversation {i} turn {j} invalid 'from' field value: {turn['from']}")
                    return False
        
        return True
    
    def _backup_corrupted_data(self):
        """Backup corrupted data file"""
        if os.path.exists(self.progress_file):
            backup_name = f"{self.progress_file}.corrupted_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            shutil.copy2(self.progress_file, backup_name)
            print(f"📋 Corrupted data backed up to: {backup_name}")
    
    def _get_generation_stats(self, conversations: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Get generation statistics"""
        if not conversations:
            return {}
        
        total_turns = sum(len(conv.get('conversations', [])) for conv in conversations)
        sample_usage = {}
        
        for conv in conversations:
            sample_id = conv.get('based_on_sample', 'unknown')
            if sample_id not in sample_usage:
                sample_usage[sample_id] = 0
            sample_usage[sample_id] += 1
        
        return {
            'total_conversations': len(conversations),
            'total_turns': total_turns,
            'avg_turns_per_conversation': total_turns / len(conversations) if conversations else 0,
            'sample_usage': sample_usage,
            'unique_samples_used': len(sample_usage)
        }
    
    def show_progress_status(self, target_count: int) -> None:
        """Show current progress status"""
        if not os.path.exists(self.progress_file):
            print("📝 Progress file not found")
            return
        

        conversations = self.load_progress()
        

        state_data = {}
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, 'r', encoding='utf-8') as f:
                    state_data = json.load(f)
            except Exception as e:
                print(f"⚠️  Failed to load state file: {e}")
        

        print("📊 Progress Status Report")
        print("=" * 50)
        print(f"📁 Progress file: {self.progress_file}")
        print(f"📅 Created at: {state_data.get('timestamp', 'unknown')}")
        print(f"🎯 Target count: {state_data.get('target_count', target_count)}")
        print(f"✅ Completed: {len(conversations)} conversations")
        print(f"⏳ Remaining: {target_count - len(conversations)} conversations")
        print(f"📈 Completion rate: {len(conversations) * 100 / target_count:.1f}%")
        

        stats = state_data.get('generation_stats', {})
        if stats:
            print(f"🔢 Total turns: {stats.get('total_turns', 'unknown')}")
            print(f"📊 Average turns: {stats.get('avg_turns_per_conversation', 0):.1f}")
            print(f"🎲 Samples used: {stats.get('unique_samples_used', 'unknown')}")
        

        file_size = os.path.getsize(self.progress_file) / 1024 / 1024
        print(f"💾 File size: {file_size:.2f} MB")
        print("=" * 50)
    
    def clean_progress_files(self, confirm: bool = False) -> None:
        """Clean progress files"""
        files_to_clean = []
        if os.path.exists(self.progress_file):
            files_to_clean.append(self.progress_file)
        if os.path.exists(self.state_file):
            files_to_clean.append(self.state_file)
        
        if not files_to_clean:
            print("📝 No progress files found to clean")
            return
        
        print(f"🗑️  Found {len(files_to_clean)} progress files:")
        for file in files_to_clean:
            file_size = os.path.getsize(file) / 1024
            print(f"  📄 {file} ({file_size:.1f} KB)")
        
        if not confirm:
            choice = input("Are you sure you want to delete these files? (y/N): ").strip().lower()
            if choice not in ['y', 'yes']:
                print("❌ Operation cancelled")
                return
        

        for file in files_to_clean:
            try:
                os.remove(file)
                print(f"✅ Deleted: {file}")
            except Exception as e:
                print(f"❌ Delete failed {file}: {e}")
    
    def backup_progress(self, backup_suffix: Optional[str] = None) -> None:
        """Backup progress files"""
        if not os.path.exists(self.progress_file):
            print("📝 Progress file not found")
            return
        
        try:
            if backup_suffix is None:
                backup_suffix = datetime.now().strftime('%Y%m%d_%H%M%S')
            
            backup_progress = f"{self.progress_file}.backup_{backup_suffix}"
            backup_state = f"{self.state_file}.backup_{backup_suffix}"
            
            shutil.copy2(self.progress_file, backup_progress)
            print(f"📋 Progress file backed up to: {backup_progress}")
            
            if os.path.exists(self.state_file):
                shutil.copy2(self.state_file, backup_state)
                print(f"📋 State file backed up to: {backup_state}")
                
        except Exception as e:
            print(f"❌ Failed to backup progress file: {e}")
    
    def has_progress(self) -> bool:
        """Check if progress file exists"""
        return os.path.exists(self.progress_file)
    
    def get_progress_count(self) -> int:
        """Get current progress count"""
        if not self.has_progress():
            return 0
        
        conversations = self.load_progress()
        return len(conversations)
    
    def is_complete(self, target_count: int) -> bool:
        """Check if complete"""
        return self.get_progress_count() >= target_count
    
    def get_remaining_count(self, target_count: int) -> int:
        """Get remaining count"""
        return max(0, target_count - self.get_progress_count())
    
    def merge_progress_files(self, progress_files: List[str]) -> List[Dict[str, Any]]:
        """Merge multiple progress files"""
        all_conversations = []
        
        for file in progress_files:
            if not os.path.exists(file):
                print(f"⚠️  File does not exist: {file}")
                continue
            
            try:
                with open(file, 'r', encoding='utf-8') as f:
                    conversations = json.load(f)
                
                if self._validate_conversations(conversations):
                    all_conversations.extend(conversations)
                    print(f"✅ Merged {len(conversations)} conversations from {file}")
                else:
                    print(f"❌ Invalid file data: {file}")
            except Exception as e:
                print(f"❌ Failed to read file {file}: {e}")
        
        print(f"🔄 Total merged {len(all_conversations)} conversations")
        return all_conversations
    
    def list_all_progress_files(self, output_dir: str) -> List[str]:
        """List all progress files"""
        progress_files = []
        

        if os.path.exists(output_dir):
            for filename in os.listdir(output_dir):
                if filename.endswith('_progress.json'):
                    progress_files.append(os.path.join(output_dir, filename))
        
        return progress_files
    
    def show_all_progress_files(self, output_dir: str) -> None:
        """Show information of all progress files"""
        progress_files = self.list_all_progress_files(output_dir)
        
        if not progress_files:
            print("📝 No progress files found")
            return
        
        print(f"🔍 Found {len(progress_files)} progress files:")
        print("=" * 80)
        
        for i, file in enumerate(progress_files, 1):
            try:

                with open(file, 'r', encoding='utf-8') as f:
                    conversations = json.load(f)
                
                state_file = file.replace('.json', '_state.json')
                state_data = {}
                if os.path.exists(state_file):
                    try:
                        with open(state_file, 'r', encoding='utf-8') as f:
                            state_data = json.load(f)
                    except:
                        pass
                
       
                file_size = os.path.getsize(file) / 1024 / 1024
                target_count = state_data.get('target_count', 'unknown')
                completion_rate = len(conversations) * 100 / target_count if isinstance(target_count, int) else 0
                
                print(f"{i}. 📄 {os.path.basename(file)}")
                print(f"   📅 Time: {state_data.get('timestamp', 'unknown')}")
                print(f"   📊 Progress: {len(conversations)}/{target_count} ({completion_rate:.1f}%)")
                print(f"   💾 Size: {file_size:.2f} MB")
                print()
                
            except Exception as e:
                print(f"{i}. 📄 {os.path.basename(file)} (Failed to read: {e})")
                print()


def create_progress_manager(output_path: str, config_hash: str) -> ProgressManager:
    """Convenience function to create progress manager"""
    return ProgressManager(output_path, config_hash) 