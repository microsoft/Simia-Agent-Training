#!/usr/bin/env python3
"""
Parallel Processing Module
Handle parallel conversation generation with worker threads and progress management
"""

import time
from typing import Dict, List, Any, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm

from .data_loader import DataLoader
from .conversation_generator import ConversationGenerator
from .progress_manager import ProgressManager


class ParallelProcessor:
    """Parallel processor"""
    
    def __init__(self, generation_settings: Dict[str, Any], data_loader: DataLoader, 
                 conversation_generator: ConversationGenerator, progress_manager: ProgressManager):
        self.generation_settings = generation_settings
        self.data_loader = data_loader
        self.conversation_generator = conversation_generator
        self.progress_manager = progress_manager
        

        self.parallel_workers = generation_settings.get('parallel_workers', 8)
        self.batch_size = generation_settings.get('batch_size', 20)
        self.rate_limit_delay = generation_settings.get('rate_limit_delay', 0.1)
        self.save_intermediate = generation_settings.get('save_progress', True)
    
    def worker_generate_conversation(self, worker_id: int, sample: Dict[str, Any], 
                                   pbar: Optional[tqdm] = None) -> Optional[Dict[str, Any]]:
        """Worker thread generates single conversation"""
        try:

            time.sleep(self.rate_limit_delay)
            
            result = self.conversation_generator.generate_conversation_with_retry(sample)
            

            if result and result.get('conversations'):

                if self.conversation_generator.validate_generated_conversation(result):
                    result = self.conversation_generator.post_process_conversation(result)
                    if pbar:
                        pbar.set_postfix({
                            'success': '✓',
                            ' conversationID': result.get('id', 'unknown')[:15] + '...',
                            ' turns': result.get('generated_turns', 0)
                        })
                    return result
                else:
                    if pbar:
                        pbar.set_postfix({'success': '✗', 'status': 'Validation failed'})
                    return None
            else:
                if pbar:
                    pbar.set_postfix({'success': '✗', 'status': 'Generation failed'})
                return None
                
        except Exception as e:
            if pbar:
                pbar.set_postfix({'success': '✗', 'error': str(e)[:20] + '...'})
            return None
    
    def process_batch(self, batch_samples: List[Dict[str, Any]], batch_number: int, 
                     total_batches: int) -> List[Dict[str, Any]]:
        """Process a single batch"""
        batch_size_actual = len(batch_samples)
        
 
        batch_pbar = tqdm(
            total=batch_size_actual,
            desc=f"📦 Batch {batch_number}/{total_batches}",
            position=1,
            leave=False,
            bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}] {postfix}"
        )
        

        batch_results = []
        with ThreadPoolExecutor(max_workers=self.parallel_workers) as executor:

            future_to_sample = {
                executor.submit(self.worker_generate_conversation, j, sample, batch_pbar): sample 
                for j, sample in enumerate(batch_samples)
            }
            

            batch_success = 0
            for future in as_completed(future_to_sample):
                result = future.result()
                if result is not None:
                    batch_results.append(result)
                    batch_success += 1
                
                batch_pbar.update(1)

                completed_tasks = batch_pbar.n
                batch_pbar.set_postfix({
                    'successful': f"{batch_success}/{completed_tasks}",
                    'success_rate': f"{batch_success*100//completed_tasks if completed_tasks > 0 else 0}%"
                })
        
        batch_pbar.close()
        return batch_results
    
    def generate_conversations_parallel(self, target_count: int, 
                                      existing_conversations: Optional[List[Dict[str, Any]]] = None) -> List[Dict[str, Any]]:
        """Generate specified number of conversations in parallel"""

        conversations = existing_conversations or []
        start_count = len(conversations)
        
        if start_count >= target_count:
            print(f"✅ Completed generation of all {target_count} conversations")
            return conversations[:target_count]
        

        remaining_count = target_count - start_count
        

        samples_to_generate = []
        for i in range(remaining_count):
            sample = self.data_loader.get_random_sample()
            samples_to_generate.append(sample)
        
        print(f"🚀 Starting parallel conversation generation")
        print(f"📊 Target: {target_count}, Completed: {start_count}, Remaining: {remaining_count}")
        print(f"⚙️  Using {self.parallel_workers} parallel workers, batch size: {self.batch_size}")
        

        total_pbar = tqdm(
            total=remaining_count,
            desc="🎯 Overall progress",
            position=0,
            leave=True,
            bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}] {postfix}"
        )

        batch_count = 0
        total_batches = (remaining_count + self.batch_size - 1) // self.batch_size
        successful_conversations = 0
        
        for i in range(0, remaining_count, self.batch_size):
            batch_count += 1
            batch_samples = samples_to_generate[i:i+self.batch_size]
            

            batch_results = self.process_batch(batch_samples, batch_count, total_batches)

            conversations.extend(batch_results)
            successful_conversations += len(batch_results)
            

            total_pbar.update(len(batch_samples))
            completed_total = total_pbar.n
            total_pbar.set_postfix({
                'successful': f"{successful_conversations}/{completed_total}",
                'success_rate': f"{successful_conversations*100//completed_total if completed_total > 0 else 0}%",
                'current_batch': f"{len(batch_results)}/{len(batch_samples)}"
            })
            

            if self.save_intermediate:
                self.progress_manager.save_progress(conversations, target_count, True)
            

            if batch_count < total_batches:
                time.sleep(self.rate_limit_delay * 2)
        
        total_pbar.close()
        
        print(f"\n🎉 All batches processing complete!")
        print(f"📈 Successfully generated {len(conversations)} conversations (success rate: {len(conversations)*100//remaining_count if remaining_count > 0 else 0}%)")
        
        return conversations[:target_count]
    
    def resume_generation(self, target_count: int) -> List[Dict[str, Any]]:
        """Resume generation progress"""
        print("🔄 Progress file detected, preparing to resume generation...")
        

        conversations = self.progress_manager.load_progress()
        
        if not conversations:
            print("📝 Progress file is empty or invalid, starting new generation")
            return self.generate_conversations_parallel(target_count)

        if len(conversations) >= target_count:
            print(f"✅ Completed generation of all {target_count} conversations")
            return conversations[:target_count]
        

        remaining = target_count - len(conversations)
        print(f"📊 Resume status:")
        print(f"   Completed: {len(conversations)} conversations")
        print(f"   Remaining: {remaining} conversations")
        print(f"   Completion rate: {len(conversations) * 100 / target_count:.1f}%")
        

        print("\nPlease select an option:")
        print("1. Continue generating remaining conversations")
        print("2. Restart generation")
        print("3. Cancel operation")
        
        while True:
            choice = input("Please enter your choice (1/2/3): ").strip()
            if choice == '1':
                print("🚀 Continuing to generate remaining conversations...")
                return self.continue_generation(conversations, target_count)
            elif choice == '2':
                print("🔄 Restarting generation...")

                self.progress_manager.backup_progress()
                return self.generate_conversations_parallel(target_count)
            elif choice == '3':
                print("❌ Operation cancelled")
                return conversations
            else:
                print("❌ Invalid choice, please try again")
    
    def continue_generation(self, existing_conversations: List[Dict[str, Any]], 
                           target_count: int) -> List[Dict[str, Any]]:
        """Continue generating remaining conversations"""
        print(f"🔄 Continuing generation from {len(existing_conversations)} conversations...")
        

        return self.generate_conversations_parallel(target_count, existing_conversations)
    
    def auto_resume_or_start(self, target_count: int) -> List[Dict[str, Any]]:
        """Automatically determine whether to resume from checkpoint"""
        if self.progress_manager.has_progress():
            print("🔍 Progress file detected, automatically using resume mode...")
            return self.resume_generation(target_count)
        else:
            print("📝 No progress file found, starting new generation...")
            return self.generate_conversations_parallel(target_count)
    
    def force_complete_from_progress(self, target_count: int) -> List[Dict[str, Any]]:
        """Force complete: retrieve existing conversations from progress file, even if target count not reached"""
        if not self.progress_manager.has_progress():
            print("❌ No progress file found")
            return []
        
        conversations = self.progress_manager.load_progress()
        
        if not conversations:
            print("❌ Progress file is empty")
            return []
        
        print(f"🔄 Retrieved {len(conversations)} conversations from progress file")
        print(f"⚠️  Note: this may be less than target count {target_count}")
        
        return conversations
    
    def get_processing_statistics(self, conversations: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Get processing statistics"""
        return self.conversation_generator.get_generation_statistics(conversations)
    
    def show_processing_summary(self, conversations: List[Dict[str, Any]]) -> None:
        """Display processing summary"""
        stats = self.get_processing_statistics(conversations)
        
        if not stats:
            print("📝 No processing statistics available")
            return
        
        print("📊 Processing Summary Report")
        print("=" * 50)
        print(f"💬 Total conversations: {stats['total_conversations']}")
        print(f"🔄 Total turns: {stats['total_turns']}")
        print(f"📊 Average turns per conversation: {stats['avg_turns_per_conversation']:.1f}")
        print(f"🎲 Samples used: {stats['unique_samples_used']}")
        
        print(f"\n📱 Sample usage details:")
        for sample_id, info in stats['sample_usage'].items():
            avg_turns = sum(info['generated_turns']) / len(info['generated_turns']) if info['generated_turns'] else 0
            print(f"  📝 {sample_id}: used {info['count']} times, sample turns {info['sample_turns']}, avg generated turns {avg_turns:.1f}")
        
        print("=" * 50)
    
    def validate_batch_results(self, batch_results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Validate batch results"""
        valid_results = []
        
        for result in batch_results:
            if self.conversation_generator.validate_generated_conversation(result):
                valid_results.append(result)
            else:
                print(f"⚠️  Invalid conversation filtered: {result.get('id', 'unknown')}")
        
        return valid_results


def create_parallel_processor(generation_settings: Dict[str, Any], data_loader: DataLoader,
                             conversation_generator: ConversationGenerator, 
                             progress_manager: ProgressManager) -> ParallelProcessor:
    """Convenience function to create parallel processor"""
    return ParallelProcessor(generation_settings, data_loader, conversation_generator, progress_manager) 