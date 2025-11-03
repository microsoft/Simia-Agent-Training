#!/usr/bin/env python3
"""
File Operations Module
Handle file saving, backup and statistics functions
"""

import json
import os
import shutil
from typing import Dict, List, Any, Optional
from datetime import datetime


class FileOperations:
    """File operations handler"""
    
    def __init__(self, output_settings: Dict[str, Any]):
        self.output_settings = output_settings
        self.output_dir = output_settings.get('output_dir', '.')
        self.backup_existing = output_settings.get('backup_existing', True)
        

        os.makedirs(self.output_dir, exist_ok=True)
    
    def save_conversations(self, conversations: List[Dict[str, Any]], output_file: str) -> None:
        """Save conversations to JSON file"""
        try:

            output_dir = os.path.dirname(output_file)
            if output_dir:
                os.makedirs(output_dir, exist_ok=True)
            

            if self.backup_existing and os.path.exists(output_file):
                backup_timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                backup_filename = f"{output_file}.backup_{backup_timestamp}"
                shutil.copy2(output_file, backup_filename)
                print(f"📋 Backup file created: {backup_filename}")
            

            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(conversations, f, ensure_ascii=False, indent=2)
            print(f"💾 Conversations saved to {output_file}")
            

            self._show_save_statistics(conversations, output_file)
            
        except Exception as e:
            print(f"❌ Failed to save file: {e}")
    
    def _show_save_statistics(self, conversations: List[Dict[str, Any]], output_file: str) -> None:
        """Display save statistics"""

        sample_usage = {}
        for conv in conversations:
            sample_id = conv.get('based_on_sample', 'unknown')
            sample_turns = conv.get('sample_turns', 0)
            generated_turns = conv.get('generated_turns', 0)
            
            if sample_id not in sample_usage:
                sample_usage[sample_id] = {
                    'count': 0,
                    'sample_turns': sample_turns,
                    'generated_turns': []
                }
            
            sample_usage[sample_id]['count'] += 1
            sample_usage[sample_id]['generated_turns'].append(generated_turns)
        
        print("\n📊 Sample usage statistics:")
        for sample_id, info in sample_usage.items():
            avg_turns = sum(info['generated_turns']) / len(info['generated_turns']) if info['generated_turns'] else 0
            print(f"  📝 {sample_id}: Used {info['count']} times, Sample turns {info['sample_turns']}, Avg generated turns {avg_turns:.1f}")
        

        total_conversations = len(conversations)
        total_generated_turns = sum(conv.get('generated_turns', 0) for conv in conversations)
        avg_turns_per_conv = total_generated_turns / total_conversations if total_conversations > 0 else 0
        
        print(f"\n📈 Overall statistics:")
        print(f"  💬 Total conversations: {total_conversations}")
        print(f"  🔄 Total generated turns: {total_generated_turns}")
        print(f"  📊 Average turns per conversation: {avg_turns_per_conv:.1f}")
        print(f"  💾 File size: {os.path.getsize(output_file) / 1024 / 1024:.2f} MB")
    
    def load_conversations(self, input_file: str) -> List[Dict[str, Any]]:
        """Load conversations from JSON file"""
        try:
            with open(input_file, 'r', encoding='utf-8') as f:
                conversations = json.load(f)
            print(f"📂 Successfully loaded {len(conversations)} conversations from {input_file}")
            return conversations
        except Exception as e:
            print(f"❌ Failed to load file: {e}")
            return []
    
    def backup_file(self, file_path: str, backup_suffix: Optional[str] = None) -> str:
        """Backup file"""
        try:
            if not os.path.exists(file_path):
                print(f"⚠️  File does not exist: {file_path}")
                return ""
            
            if backup_suffix is None:
                backup_suffix = datetime.now().strftime('%Y%m%d_%H%M%S')
            
            backup_path = f"{file_path}.backup_{backup_suffix}"
            shutil.copy2(file_path, backup_path)
            print(f"📋 File backed up to: {backup_path}")
            return backup_path
            
        except Exception as e:
            print(f"❌ Failed to backup file: {e}")
            return ""
    
    def delete_file(self, file_path: str, confirm: bool = False) -> bool:
        """Delete file"""
        try:
            if not os.path.exists(file_path):
                print(f"⚠️  File does not exist: {file_path}")
                return False
            
            if not confirm:
                file_size = os.path.getsize(file_path) / 1024
                print(f"🗑️  About to delete file: {file_path} ({file_size:.1f} KB)")
                choice = input("Are you sure you want to delete? (y/N): ").strip().lower()
                if choice not in ['y', 'yes']:
                    print("❌ Operation cancelled")
                    return False
            
            os.remove(file_path)
            print(f"✅ File deleted: {file_path}")
            return True
            
        except Exception as e:
            print(f"❌ Failed to delete file: {e}")
            return False
    
    def get_file_info(self, file_path: str) -> Dict[str, Any]:
        """Get file information"""
        try:
            if not os.path.exists(file_path):
                return {}
            
            stat = os.stat(file_path)
            return {
                'path': file_path,
                'size_bytes': stat.st_size,
                'size_mb': stat.st_size / 1024 / 1024,
                'created_time': datetime.fromtimestamp(stat.st_ctime).isoformat(),
                'modified_time': datetime.fromtimestamp(stat.st_mtime).isoformat(),
                'exists': True
            }
            
        except Exception as e:
            print(f"❌ Failed to get file information: {e}")
            return {'exists': False}
    
    def list_files_in_directory(self, directory: str, pattern: str = "*.json") -> List[str]:
        """List files in directory"""
        try:
            if not os.path.exists(directory):
                return []
            
            import glob
            pattern_path = os.path.join(directory, pattern)
            files = glob.glob(pattern_path)
            return sorted(files)
            
        except Exception as e:
            print(f"❌ Failed to list files: {e}")
            return []
    
    def validate_json_file(self, file_path: str) -> bool:
        """Validate JSON file format"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                json.load(f)
            return True
        except json.JSONDecodeError as e:
            print(f"❌ JSON format error: {e}")
            return False
        except Exception as e:
            print(f"❌ File validation failed: {e}")
            return False
    
    def merge_json_files(self, input_files: List[str], output_file: str) -> bool:
        """Merge multiple JSON files"""
        try:
            all_data = []
            
            for file_path in input_files:
                if not os.path.exists(file_path):
                    print(f"⚠️  File does not exist: {file_path}")
                    continue
                
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        all_data.extend(data)
                        print(f"✅ Merged {len(data)} records from {file_path}")
                    else:
                        print(f"⚠️  File format is not a list: {file_path}")
            
            if all_data:
                with open(output_file, 'w', encoding='utf-8') as f:
                    json.dump(all_data, f, ensure_ascii=False, indent=2)
                print(f"🔄 Total merged {len(all_data)} records to {output_file}")
                return True
            else:
                print("❌ No data to merge")
                return False
                
        except Exception as e:
            print(f"❌ Failed to merge files: {e}")
            return False
    
    def split_json_file(self, input_file: str, output_dir: str, chunk_size: int = 1000) -> List[str]:
        """Split JSON file"""
        try:
            with open(input_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            if not isinstance(data, list):
                print("❌ Input file is not in list format")
                return []
            
            os.makedirs(output_dir, exist_ok=True)
            
            output_files = []
            base_name = os.path.splitext(os.path.basename(input_file))[0]
            
            for i in range(0, len(data), chunk_size):
                chunk = data[i:i + chunk_size]
                chunk_file = os.path.join(output_dir, f"{base_name}_part_{i//chunk_size + 1}.json")
                
                with open(chunk_file, 'w', encoding='utf-8') as f:
                    json.dump(chunk, f, ensure_ascii=False, indent=2)
                
                output_files.append(chunk_file)
                print(f"✅ Created chunk file: {chunk_file} ({len(chunk)} records)")
            
            print(f"🔄 Total created {len(output_files)} chunk files")
            return output_files
            
        except Exception as e:
            print(f"❌ Failed to split file: {e}")
            return []
    
    def calculate_directory_size(self, directory: str) -> Dict[str, Any]:
        """Calculate directory size"""
        try:
            total_size = 0
            file_count = 0
            
            for dirpath, dirnames, filenames in os.walk(directory):
                for filename in filenames:
                    file_path = os.path.join(dirpath, filename)
                    try:
                        total_size += os.path.getsize(file_path)
                        file_count += 1
                    except OSError:
                        continue
            
            return {
                'total_size_bytes': total_size,
                'total_size_mb': total_size / 1024 / 1024,
                'total_size_gb': total_size / 1024 / 1024 / 1024,
                'file_count': file_count,
                'directory': directory
            }
            
        except Exception as e:
            print(f"❌ Failed to calculate directory size: {e}")
            return {}
    
    def clean_directory(self, directory: str, pattern: str = "*.json", confirm: bool = False) -> int:
        """Clean files in directory"""
        try:
            files_to_delete = self.list_files_in_directory(directory, pattern)
            
            if not files_to_delete:
                print("📝 No files found to delete")
                return 0
            
            if not confirm:
                total_size = sum(os.path.getsize(f) for f in files_to_delete) / 1024 / 1024
                print(f"🗑️  Found {len(files_to_delete)} files, total size {total_size:.2f} MB")
                choice = input("Are you sure you want to delete these files? (y/N): ").strip().lower()
                if choice not in ['y', 'yes']:
                    print("❌ Operation cancelled")
                    return 0
            
            deleted_count = 0
            for file_path in files_to_delete:
                try:
                    os.remove(file_path)
                    deleted_count += 1
                    print(f"✅ Deleted: {os.path.basename(file_path)}")
                except Exception as e:
                    print(f"❌ Delete failed {file_path}: {e}")
            
            print(f"🎉 Successfully deleted {deleted_count} files")
            return deleted_count
            
        except Exception as e:
            print(f"❌ Failed to clean directory: {e}")
            return 0


def create_file_operations(output_settings: Dict[str, Any]) -> FileOperations:
    """Convenience function to create file operations handler"""
    return FileOperations(output_settings) 