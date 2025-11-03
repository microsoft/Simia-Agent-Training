#!/usr/bin/env python3
"""
Main Generator Module - AgentTuning Version
Integrate all functional modules, provide unified interface for generating Agent trajectory conversations
"""

from typing import Dict, List, Any, Optional

from .config import ConfigManager
from .gpt_logger import GPTLogger
from .data_loader import DataLoader
from .conversation_generator import ConversationGenerator
from .progress_manager import ProgressManager
from .file_operations import FileOperations
from .parallel_processor import ParallelProcessor


class ShareGPTGenerator:
    """Agent trajectory conversations generator main class"""
    
    def __init__(self, config_path: str = 'config.json'):
        self.config_manager = ConfigManager(config_path)
        
        if not self.config_manager.validate_config():
            raise ValueError("Configuration validation failed")
        
        self.azure_config = self.config_manager.get_azure_config()
        self.generation_settings = self.config_manager.get_generation_settings()
        self.output_settings = self.config_manager.get_output_settings()
        self.gpt_log_settings = self.config_manager.get_gpt_log_settings()
        self.sample_data_path = self.config_manager.get_sample_data_path()
        

        self.full_output_path = self.config_manager.get_full_output_path()
        self.full_gpt_log_path = self.config_manager.get_full_gpt_log_path()
        

        self.gpt_logger = GPTLogger(
            self.full_gpt_log_path, 
            self.gpt_log_settings['enable_logging'],
            self.azure_config
        )
        
        self.data_loader = DataLoader(
            self.sample_data_path
        )
        
        self.conversation_generator = ConversationGenerator(
            self.azure_config,
            self.generation_settings,
            self.data_loader,
            self.gpt_logger
        )
        
        self.progress_manager = ProgressManager(
            self.full_output_path,
            self.config_manager.get_config_hash()
        )
        
        self.file_operations = FileOperations(
            self.output_settings
        )
        
        self.parallel_processor = ParallelProcessor(
            self.generation_settings,
            self.data_loader,
            self.conversation_generator,
            self.progress_manager
        )
        

        self.max_conversations = self.generation_settings['max_conversations']
        
        print(f"🚀 ShareGPT generator initialized")
        print(f"📁 Output File: {self.full_output_path}")
        print(f"🎯 Target Count: {self.max_conversations}")
    
    def generate_conversations(self, num_conversations: Optional[int] = None) -> List[Dict[str, Any]]:
        """Generate conversations"""
        target_count = num_conversations if num_conversations is not None else self.max_conversations
        return self.parallel_processor.generate_conversations_parallel(target_count)
    
    def resume_generation(self) -> List[Dict[str, Any]]:
        """Resume generation progress"""
        return self.parallel_processor.resume_generation(self.max_conversations)
    
    def auto_resume_or_start(self) -> List[Dict[str, Any]]:
        """Auto determine whether to resume or start"""
        return self.parallel_processor.auto_resume_or_start(self.max_conversations)
    
    def force_complete_from_progress(self) -> List[Dict[str, Any]]:
        """Force complete: Get existing conversations from progress file"""
        return self.parallel_processor.force_complete_from_progress(self.max_conversations)
    
    def save_conversations(self, conversations: List[Dict[str, Any]], 
                          filename: Optional[str] = None) -> None:
        """Save conversations to file"""
        output_file = filename or self.full_output_path
        self.file_operations.save_conversations(conversations, output_file)
    
    def load_conversations(self, filename: Optional[str] = None) -> List[Dict[str, Any]]:
        """Load conversations from file"""
        input_file = filename or self.full_output_path
        return self.file_operations.load_conversations(input_file)
    
    def show_progress_status(self) -> None:
        """Show progress status"""
        self.progress_manager.show_progress_status(self.max_conversations)
    
    def clean_progress_files(self, confirm: bool = False) -> None:
        """Clean progress files"""
        self.progress_manager.clean_progress_files(confirm)
    
    def show_all_progress_files(self) -> None:
        """Show all progress files"""
        self.progress_manager.show_all_progress_files(self.output_settings['output_dir'])
    
    def merge_progress_files(self, progress_files: List[str]) -> List[Dict[str, Any]]:
        """Merge multiple progress files"""
        return self.progress_manager.merge_progress_files(progress_files)
    
    def show_gpt_log_stats(self) -> None:
        """Show GPT log statistics"""
        self.gpt_logger.show_log_stats()
    
    def export_gpt_log_summary(self, output_file: Optional[str] = None) -> None:
        """Export GPT log summary"""
        self.gpt_logger.export_log_summary(output_file)
    
    def show_sample_statistics(self) -> None:
        """Show sample data statistics"""
        self.data_loader.show_sample_statistics()
    
    def validate_sample_data(self) -> bool:
        """Validate sample data"""
        return self.data_loader.validate_sample_data()
    
    def show_processing_summary(self, conversations: List[Dict[str, Any]]) -> None:
        """Show processing summary"""
        self.parallel_processor.show_processing_summary(conversations)
    
    def backup_files(self, backup_suffix: Optional[str] = None) -> None:
        """Backup important files"""
        self.progress_manager.backup_progress(backup_suffix)
        self.gpt_logger.backup_log(backup_suffix)
    
    def get_generation_statistics(self, conversations: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Get generation statistics"""
        return self.parallel_processor.get_processing_statistics(conversations)
    
    def has_progress(self) -> bool:
        """Check if has progress"""
        return self.progress_manager.has_progress()
    
    def get_progress_count(self) -> int:
        """Get current progress count"""
        return self.progress_manager.get_progress_count()
    
    def is_complete(self) -> bool:
        """Check if complete"""
        return self.progress_manager.is_complete(self.max_conversations)
    
    def get_remaining_count(self) -> int:
        """Get remaining count"""
        return self.progress_manager.get_remaining_count(self.max_conversations)
    
    def get_completion_rate(self) -> float:
        """Get completion rate"""
        return self.get_progress_count() / self.max_conversations if self.max_conversations > 0 else 0.0
    
    def generate_single_conversation(self, sample: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Generate single conversation (for testing)"""
        if sample is None:
            sample = self.data_loader.get_random_sample()
        return self.conversation_generator.generate_conversation_with_retry(sample)
    
    def validate_generated_conversation(self, conv: Dict[str, Any]) -> bool:
        """Validate generated conversation"""
        return self.conversation_generator.validate_generated_conversation(conv)
    
    def run_interactive_mode(self) -> List[Dict[str, Any]]:
        """Run interactive mode"""
        print("🎮 Entering interactive mode")
        print("=" * 50)
        

        if self.has_progress():
            print(f"📊 Current progress: {self.get_progress_count()}/{self.max_conversations} ({self.get_completion_rate():.1%})")
        else:
            print("📝 No progress file found")
        

        print("\nAvailable operations:")
        print("1. Start new generation")
        print("2. Resume progress")
        print("3. Auto select (recommended)")
        print("4. Show progress status")
        print("5. Show GPT log statistics")
        print("6. Show sample statistics")
        print("7. Clean progress files")
        print("8. Exit")
        
        while True:
            choice = input("\nPlease select operation (1-8): ").strip()
            
            if choice == '1':
                print("🚀 Starting new generation...")
                conversations = self.generate_conversations()
                self.save_conversations(conversations)
                return conversations
            
            elif choice == '2':
                print("🔄 Resuming progress...")
                conversations = self.resume_generation()
                self.save_conversations(conversations)
                return conversations
            
            elif choice == '3':
                print("🎯 Auto selecting...")
                conversations = self.auto_resume_or_start()
                self.save_conversations(conversations)
                return conversations
            
            elif choice == '4':
                self.show_progress_status()
                
            elif choice == '5':
                self.show_gpt_log_stats()
                
            elif choice == '6':
                self.show_sample_statistics()
                
            elif choice == '7':
                self.clean_progress_files()
                
            elif choice == '8':
                print("👋 Exiting program")
                return []
            
            else:
                print("❌ Invalid selection, please try again")
    
    def get_system_info(self) -> Dict[str, Any]:
        """Get system information"""
        return {
            'config_path': self.config_manager.config_path,
            'output_path': self.full_output_path,
            'gpt_log_path': self.full_gpt_log_path,
            'target_conversations': self.max_conversations,
            'current_progress': self.get_progress_count(),
            'completion_rate': self.get_completion_rate(),
            'has_progress': self.has_progress(),
            'azure_config': self.azure_config,
            'generation_settings': self.generation_settings,
            'sample_data_path': self.sample_data_path,
            'sample_count': len(self.data_loader.sample_conversations)
        }
    
    def show_system_info(self) -> None:
        """Show system information"""
        info = self.get_system_info()
        
        print("🔍 System Information")
        print("=" * 50)
        print(f"📄 Configuration File: {info['config_path']}")
        print(f"📁 Output File: {info['output_path']}")
        print(f"📋 GPT Log: {info['gpt_log_path']}")
        print(f"🎯 Target Count: {info['target_conversations']}")
        print(f"📊 Current Progress: {info['current_progress']}")
        print(f"📈 Completion Rate: {info['completion_rate']:.1%}")
        print(f"📝 Has Progress File: {'Yes' if info['has_progress'] else 'No'}")
        print(f"🗂️  Sample Data: {info['sample_data_path']}")
        print(f"📦 Sample Count: {info['sample_count']}")
        print(f"🤖 Model: {info['azure_config']['deployment']}")
        print(f"🌡️  Temperature: {info['generation_settings']['temperature']}")
        print(f"🎪 Max Tokens: {info['generation_settings']['max_tokens']}")
        print(f"🔄 Retry Attempts: {info['generation_settings']['retry_attempts']}")
        print(f"⚙️  Parallel Workers: {info['generation_settings']['parallel_workers']}")
        print("=" * 50)


def create_share_gpt_generator(config_path: str = 'config.json') -> ShareGPTGenerator:
    """Convenience function to create ShareGPT generator"""
    return ShareGPTGenerator(config_path) 