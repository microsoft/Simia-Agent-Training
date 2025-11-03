#!/usr/bin/env python3
"""
GPT Logger Module
Handle GPT call logging, statistics and analysis
"""

import json
import os
from typing import Dict, Any, Optional, List
from datetime import datetime
from collections import Counter


class GPTLogger:
    """GPT call logger"""
    
    def __init__(self, log_file_path: str, enable_logging: bool = True, azure_config: Optional[Dict[str, Any]] = None):
        self.log_file_path = log_file_path
        self.enable_logging = enable_logging
        self.azure_config = azure_config or {}
        
        if self.enable_logging:
            self.init_log_file()
            print(f"🔊 GPT output logging enabled: {self.log_file_path}")
    
    def init_log_file(self):
        """Initialize GPT log file"""
        try:

            if not os.path.exists(self.log_file_path):
                with open(self.log_file_path, 'w', encoding='utf-8') as f:
                    header = {
                        "log_type": "gpt_outputs",
                        "created_at": datetime.now().isoformat(),
                        "config": {
                            "model": self.azure_config.get('deployment', 'gpt-4o'),
                            "api_version": self.azure_config.get('api_version', '2024-08-01-preview')
                        }
                    }
                    f.write(json.dumps(header, ensure_ascii=False) + '\n')
        except Exception as e:
            print(f"⚠️ Failed to initialize GPT log file: {e}")
    
    def log_gpt_call(self, prompt: str, response: str, sample_id: str = "", attempt: int = 1, 
                     error: Optional[str] = None, duration: float = 0.0, tokens_used: Optional[dict] = None):
        """Log GPT call"""
        if not self.enable_logging:
            return
            
        try:
            log_entry = {
                "timestamp": datetime.now().isoformat(),
                "sample_id": sample_id,
                "attempt": attempt,
                "duration_seconds": duration,
                "tokens_used": tokens_used or {},
                "prompt": prompt,
                "response": response,
                "error": error,
                "success": error is None
            }
            
            with open(self.log_file_path, 'a', encoding='utf-8') as f:
                f.write(json.dumps(log_entry, ensure_ascii=False) + '\n')
                
        except Exception as e:
            print(f"⚠️ Failed to log GPT call: {e}")
    
    def get_log_stats(self) -> Dict[str, Any]:
        """Get GPT log statistics"""
        if not self.enable_logging or not os.path.exists(self.log_file_path):
            return {}
        
        stats = {
            "total_calls": 0,
            "successful_calls": 0,
            "failed_calls": 0,
            "total_duration": 0.0,
            "total_tokens": 0,
            "retry_attempts": 0,
            "unique_samples": set(),
            "errors": []
        }
        
        try:
            with open(self.log_file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.strip():
                        try:
                            entry = json.loads(line.strip())
                            

                            if entry.get('log_type') == 'gpt_outputs':
                                continue
                            
                            stats["total_calls"] += 1
                            if entry.get('success', False):
                                stats["successful_calls"] += 1
                            else:
                                stats["failed_calls"] += 1
                                if entry.get('error'):
                                    stats["errors"].append(entry['error'])
                            
                            stats["total_duration"] += entry.get('duration_seconds', 0)
                            
                            tokens = entry.get('tokens_used', {})
                            if isinstance(tokens, dict):
                                stats["total_tokens"] += tokens.get('total_tokens', 0)
                            
                            if entry.get('attempt', 1) > 1:
                                stats["retry_attempts"] += 1
                            
                            sample_id = entry.get('sample_id', '')
                            if sample_id and sample_id != 'unknown':
                                stats["unique_samples"].add(sample_id)
                        
                        except json.JSONDecodeError:
                            continue
            
            stats["unique_samples"] = len(stats["unique_samples"])
            stats["avg_duration"] = stats["total_duration"] / stats["total_calls"] if stats["total_calls"] > 0 else 0
            stats["success_rate"] = stats["successful_calls"] / stats["total_calls"] if stats["total_calls"] > 0 else 0
            
        except Exception as e:
            print(f"⚠️ Failed to read GPT log: {e}")
            return {}
        
        return stats
    
    def show_log_stats(self):
        """Show GPT log statistics"""
        stats = self.get_log_stats()
        
        if not stats:
            print("📝 No GPT log data found")
            return
        
        print("📊 GPT Call Statistics Report")
        print("=" * 50)
        print(f"📞 Total calls: {stats['total_calls']}")
        print(f"✅ Successful calls: {stats['successful_calls']}")
        print(f"❌ Failed calls: {stats['failed_calls']}")
        print(f"📈 Success rate: {stats['success_rate']:.2%}")
        print(f"🔄 Retry attempts: {stats['retry_attempts']}")
        print(f"⏱️  Total duration: {stats['total_duration']:.2f}s")
        print(f"⚡ Average duration: {stats['avg_duration']:.2f}s")
        print(f"🎯 Samples used: {stats['unique_samples']}")
        print(f"🎪 Total tokens: {stats['total_tokens']}")
        
        if stats['errors']:
            print(f"\n❌ Error type statistics:")
            error_counts = Counter(stats['errors'])
            for error, count in error_counts.most_common(5):
                print(f"   {error}: {count} times")
        
        print("=" * 50)
    
    def export_log_summary(self, output_file: Optional[str] = None):
        """Export GPT log summary to file"""
        if output_file is None:
            output_file = self.log_file_path.replace('.jsonl', '_summary.json')
        
        stats = self.get_log_stats()
        
        if not stats:
            print("📝 No GPT log data found")
            return
        

        detailed_entries = []
        try:
            with open(self.log_file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.strip():
                        try:
                            entry = json.loads(line.strip())
                            if entry.get('log_type') != 'gpt_outputs': 
                                summary_entry = {
                                    "timestamp": entry.get('timestamp'),
                                    "sample_id": entry.get('sample_id'),
                                    "attempt": entry.get('attempt'),
                                    "duration_seconds": entry.get('duration_seconds'),
                                    "tokens_used": entry.get('tokens_used'),
                                    "success": entry.get('success'),
                                    "error": entry.get('error'),
                                    "prompt_length": len(entry.get('prompt', '')),
                                    "response_length": len(entry.get('response', ''))
                                }
                                detailed_entries.append(summary_entry)
                        except json.JSONDecodeError:
                            continue
        except Exception as e:
            print(f"⚠️ Failed to read detailed log: {e}")
        
        summary = {
            "generated_at": datetime.now().isoformat(),
            "log_file": self.log_file_path,
            "statistics": stats,
            "detailed_entries": detailed_entries
        }
        
        try:
            final_output_file = output_file or self.log_file_path.replace('.jsonl', '_summary.json')
            with open(final_output_file, 'w', encoding='utf-8') as f:
                json.dump(summary, f, ensure_ascii=False, indent=2)
            print(f"📋 GPT log summary exported to: {final_output_file}")
        except Exception as e:
            print(f"❌ Failed to export GPT log summary: {e}")
    
    def get_detailed_entries(self) -> List[Dict[str, Any]]:
        """Get detailed log entries"""
        detailed_entries = []
        
        if not self.enable_logging or not os.path.exists(self.log_file_path):
            return detailed_entries
        
        try:
            with open(self.log_file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.strip():
                        try:
                            entry = json.loads(line.strip())
                            if entry.get('log_type') != 'gpt_outputs':  
                                detailed_entries.append(entry)
                        except json.JSONDecodeError:
                            continue
        except Exception as e:
            print(f"⚠️ Failed to read detailed log: {e}")
        
        return detailed_entries
    
    def clear_log(self):
        """Clear log file"""
        if not self.enable_logging:
            return
        
        try:
            if os.path.exists(self.log_file_path):
                os.remove(self.log_file_path)
                print(f"🗑️  Cleared GPT log file: {self.log_file_path}")
                self.init_log_file()
        except Exception as e:
            print(f"❌ Failed to clear GPT log: {e}")
    
    def backup_log(self, backup_suffix: Optional[str] = None):
        """Backup log file"""
        if not self.enable_logging or not os.path.exists(self.log_file_path):
            return
        
        try:
            if backup_suffix is None:
                backup_suffix = datetime.now().strftime('%Y%m%d_%H%M%S')
            
            backup_path = f"{self.log_file_path}.backup_{backup_suffix}"
            
            import shutil
            shutil.copy2(self.log_file_path, backup_path)
            print(f"📋 GPT log backed up to: {backup_path}")
            
        except Exception as e:
            print(f"❌ Failed to backup GPT log: {e}")


def create_gpt_logger(log_file_path: str, enable_logging: bool = True, 
                     azure_config: Optional[Dict[str, Any]] = None) -> GPTLogger:
    """Convenience function to create GPT logger"""
    return GPTLogger(log_file_path, enable_logging, azure_config) 