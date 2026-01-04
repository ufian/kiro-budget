"""
User interaction and learning capabilities for transaction categorization.
"""

import logging
from typing import List, Optional, Dict, Any, Callable
from datetime import datetime

from .models import Transaction, CategoryResult
from .category_engine import CategoryEngine


class UserInteraction:
    """
    Handles manual categorization requests and learns from user feedback
    to improve future categorization accuracy.
    """
    
    def __init__(self, category_engine: CategoryEngine, 
                 input_function: Callable[[str], str] = None,
                 print_function: Callable[[str], None] = None):
        """
        Initialize user interaction handler.
        
        Args:
            category_engine: CategoryEngine instance for learning
            input_function: Function to get user input (defaults to input())
            print_function: Function to print messages (defaults to print())
        """
        self.logger = logging.getLogger(__name__)
        self.category_engine = category_engine
        
        # Allow dependency injection for testing
        self.input_function = input_function or input
        self.print_function = print_function or print
        
        # Learning statistics
        self.learning_stats = {
            "manual_categorizations": 0,
            "patterns_learned": 0,
            "inconsistencies_detected": 0,
            "batch_reviews_completed": 0
        }
    
    def request_manual_categorization(self, transaction: Transaction, 
                                    suggestions: List[str] = None) -> str:
        """
        Request manual categorization from user with interactive prompts.
        
        Args:
            transaction: Transaction to categorize
            suggestions: Optional list of suggested categories
            
        Returns:
            User-selected category name
        """
        self.print_function("\n" + "="*60)
        self.print_function("MANUAL CATEGORIZATION REQUIRED")
        self.print_function("="*60)
        
        # Display transaction details
        self.print_function(f"Date: {transaction.date.strftime('%Y-%m-%d')}")
        self.print_function(f"Amount: ${abs(transaction.amount):.2f}")
        self.print_function(f"Description: {transaction.description}")
        self.print_function(f"Account: {transaction.account}")
        self.print_function(f"Institution: {transaction.institution}")
        
        # Show available categories
        available_categories = self.category_engine.get_available_categories()
        if not available_categories:
            available_categories = ["Uncategorized"]
        
        self.print_function(f"\nAvailable categories:")
        for i, category in enumerate(available_categories, 1):
            marker = " (suggested)" if suggestions and category in suggestions else ""
            self.print_function(f"  {i}. {category}{marker}")
        
        # Add option for new category
        self.print_function(f"  {len(available_categories) + 1}. Create new category")
        
        # Get user selection
        while True:
            try:
                choice = self.input_function(f"\nSelect category (1-{len(available_categories) + 1}): ").strip()
                
                if choice.isdigit():
                    choice_num = int(choice)
                    if 1 <= choice_num <= len(available_categories):
                        selected_category = available_categories[choice_num - 1]
                        break
                    elif choice_num == len(available_categories) + 1:
                        # Create new category
                        selected_category = self._create_new_category()
                        if selected_category:
                            break
                    else:
                        self.print_function("Invalid selection. Please try again.")
                else:
                    # Allow direct category name input
                    if choice in available_categories:
                        selected_category = choice
                        break
                    else:
                        self.print_function(f"Category '{choice}' not found. Please select from the list or create new.")
                        
            except (ValueError, KeyboardInterrupt):
                self.print_function("Invalid input. Please try again.")
        
        self.learning_stats["manual_categorizations"] += 1
        self.print_function(f"Selected category: {selected_category}")
        
        return selected_category
    
    def display_categorization_options(self, suggestions: List[str]) -> str:
        """
        Display categorization options and get user selection.
        
        Args:
            suggestions: List of suggested categories
            
        Returns:
            Selected category name
        """
        if not suggestions:
            return "Uncategorized"
        
        self.print_function("\nSuggested categories:")
        for i, suggestion in enumerate(suggestions, 1):
            self.print_function(f"  {i}. {suggestion}")
        
        self.print_function(f"  {len(suggestions) + 1}. Other (manual entry)")
        
        while True:
            try:
                choice = self.input_function(f"Select category (1-{len(suggestions) + 1}): ").strip()
                
                if choice.isdigit():
                    choice_num = int(choice)
                    if 1 <= choice_num <= len(suggestions):
                        return suggestions[choice_num - 1]
                    elif choice_num == len(suggestions) + 1:
                        return self.input_function("Enter category name: ").strip()
                
                self.print_function("Invalid selection. Please try again.")
                
            except (ValueError, KeyboardInterrupt):
                self.print_function("Invalid input. Please try again.")
    
    def learn_from_feedback(self, transaction: Transaction, category: str, 
                          confidence: float = 0.9) -> None:
        """
        Learn from user feedback by creating pattern rules and updating ML model.
        
        Args:
            transaction: Transaction that was manually categorized
            category: User-selected category
            confidence: Confidence score for the learned pattern
        """
        try:
            # Create pattern rules from manual categorization
            created_patterns = self.create_pattern_rule_from_manual_categorization(
                transaction, category, user_confirmed=True
            )
            
            if created_patterns:
                self.logger.info(f"Learned {len(created_patterns)} patterns from feedback: "
                               f"{created_patterns} -> {category}")
            
            # Update ML model with user correction if available
            self._update_ml_model_with_feedback(transaction, category)
            
            # Check for similar transactions that might need updating
            self._update_similar_transactions(transaction, category)
            
            # Log the learning event
            self.logger.info(f"Learned from feedback: '{transaction.description}' -> {category}")
            
        except Exception as e:
            self.logger.error(f"Failed to learn from feedback: {e}")
    
    def _update_ml_model_with_feedback(self, transaction: Transaction, category: str) -> None:
        """
        Update ML model with user correction feedback.
        
        Args:
            transaction: Transaction with user correction
            category: Correct category from user
        """
        try:
            # Check if ML categorizer is available
            if hasattr(self.category_engine, 'ml_categorizer') and self.category_engine.ml_categorizer:
                self.category_engine.ml_categorizer.update_with_feedback(transaction, category)
                self.logger.info(f"Updated ML model with feedback: {transaction.description} -> {category}")
        except Exception as e:
            self.logger.warning(f"Failed to update ML model with feedback: {e}")
    
    def _update_similar_transactions(self, transaction: Transaction, category: str) -> None:
        """
        Find and suggest updates for similar transactions.
        
        Args:
            transaction: Reference transaction
            category: Category to apply to similar transactions
        """
        try:
            # This would typically work with a transaction database
            # For now, we log the suggestion for manual review
            self.logger.info(f"Consider updating similar transactions to '{transaction.description}' with category '{category}'")
        except Exception as e:
            self.logger.warning(f"Failed to update similar transactions: {e}")
    
    def batch_review_low_confidence(self, transactions: List[Transaction], 
                                  confidence_threshold: float = 0.7) -> Dict[str, Any]:
        """
        Review multiple low-confidence transactions in batch.
        
        Args:
            transactions: List of transactions to review
            confidence_threshold: Confidence threshold for review
            
        Returns:
            Dictionary with review results and statistics
        """
        if not transactions:
            return {"reviewed": 0, "learned": 0, "skipped": 0}
        
        self.print_function(f"\n{'='*60}")
        self.print_function(f"BATCH REVIEW: {len(transactions)} transactions")
        self.print_function(f"{'='*60}")
        
        results = {"reviewed": 0, "learned": 0, "skipped": 0}
        
        for i, transaction in enumerate(transactions, 1):
            # Get current categorization
            current_result = self.category_engine.categorize_transaction(transaction)
            
            # Skip if confidence is above threshold
            if current_result.confidence >= confidence_threshold:
                results["skipped"] += 1
                continue
            
            self.print_function(f"\nTransaction {i}/{len(transactions)}")
            self.print_function(f"Current: {current_result.category} (confidence: {current_result.confidence:.2f})")
            
            # Ask user for review
            review_choice = self.input_function("Review this transaction? (y/n/q): ").strip().lower()
            
            if review_choice == 'q':
                self.print_function("Batch review cancelled.")
                break
            elif review_choice == 'y':
                # Get manual categorization
                suggestions = [current_result.category] if current_result.confidence > 0.3 else []
                manual_category = self.request_manual_categorization(transaction, suggestions)
                
                # Learn from feedback if different from current
                if manual_category != current_result.category:
                    self.learn_from_feedback(transaction, manual_category)
                    results["learned"] += 1
                
                results["reviewed"] += 1
            else:
                results["skipped"] += 1
        
        self.learning_stats["batch_reviews_completed"] += 1
        
        self.print_function(f"\nBatch review completed:")
        self.print_function(f"  Reviewed: {results['reviewed']}")
        self.print_function(f"  Learned: {results['learned']}")
        self.print_function(f"  Skipped: {results['skipped']}")
        
        return results
    
    def detect_inconsistencies(self, transactions: List[Transaction], 
                             similarity_threshold: float = 0.8) -> List[Dict[str, Any]]:
        """
        Detect categorization inconsistencies in similar transactions.
        
        Args:
            transactions: List of transactions to analyze
            similarity_threshold: Similarity threshold for grouping
            
        Returns:
            List of inconsistency reports
        """
        inconsistencies = []
        
        # Group similar transactions
        similar_groups = self._group_similar_transactions(transactions, similarity_threshold)
        
        for group in similar_groups:
            if len(group) < 2:
                continue
            
            # Get categories for all transactions in group
            categories = {}
            for transaction in group:
                result = self.category_engine.categorize_transaction(transaction)
                category = result.category
                if category not in categories:
                    categories[category] = []
                categories[category].append({
                    'transaction': transaction,
                    'result': result
                })
            
            # Check for inconsistencies (multiple categories for similar transactions)
            if len(categories) > 1:
                inconsistency = {
                    "group_size": len(group),
                    "categories": {cat: len(txns) for cat, txns in categories.items()},
                    "sample_descriptions": [t.description for t in group[:3]],
                    "transactions": group,
                    "category_details": categories,
                    "confidence_scores": {
                        cat: [item['result'].confidence for item in items]
                        for cat, items in categories.items()
                    }
                }
                inconsistencies.append(inconsistency)
                self.learning_stats["inconsistencies_detected"] += 1
        
        return inconsistencies
    
    def suggest_category_fixes(self, inconsistencies: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Suggest fixes for detected inconsistencies.
        
        Args:
            inconsistencies: List of inconsistency reports
            
        Returns:
            List of suggested fixes with reasoning
        """
        if not inconsistencies:
            self.print_function("No inconsistencies detected.")
            return []
        
        suggestions = []
        
        self.print_function(f"\nDetected {len(inconsistencies)} inconsistencies:")
        
        for i, inconsistency in enumerate(inconsistencies, 1):
            self.print_function(f"\nInconsistency {i}:")
            self.print_function(f"  Group size: {inconsistency['group_size']} transactions")
            self.print_function(f"  Categories: {inconsistency['categories']}")
            self.print_function(f"  Sample descriptions:")
            for desc in inconsistency['sample_descriptions']:
                self.print_function(f"    - {desc}")
            
            # Analyze confidence scores to suggest best category
            suggestion = self._analyze_inconsistency_for_suggestion(inconsistency)
            suggestions.append(suggestion)
            
            self.print_function(f"  Suggestion: {suggestion['recommendation']}")
            self.print_function(f"  Reasoning: {suggestion['reasoning']}")
        
        return suggestions
    
    def _analyze_inconsistency_for_suggestion(self, inconsistency: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze an inconsistency to provide the best suggestion.
        
        Args:
            inconsistency: Inconsistency report
            
        Returns:
            Dictionary with suggestion details
        """
        categories = inconsistency['categories']
        confidence_scores = inconsistency['confidence_scores']
        
        # Find category with highest average confidence
        avg_confidences = {}
        for category, scores in confidence_scores.items():
            avg_confidences[category] = sum(scores) / len(scores) if scores else 0.0
        
        # Find most frequent category
        most_frequent_category = max(categories.items(), key=lambda x: x[1])
        
        # Find highest confidence category
        highest_confidence_category = max(avg_confidences.items(), key=lambda x: x[1])
        
        # Decision logic for recommendation
        if most_frequent_category[1] > len(inconsistency['transactions']) * 0.6:
            # If one category appears in >60% of transactions, recommend it
            recommended_category = most_frequent_category[0]
            reasoning = f"Most frequent category ({most_frequent_category[1]}/{inconsistency['group_size']} transactions)"
        elif highest_confidence_category[1] > 0.8:
            # If one category has high confidence, recommend it
            recommended_category = highest_confidence_category[0]
            reasoning = f"Highest confidence category (avg confidence: {highest_confidence_category[1]:.2f})"
        else:
            # Default to most frequent
            recommended_category = most_frequent_category[0]
            reasoning = f"Most frequent category (confidence analysis inconclusive)"
        
        return {
            'inconsistency_id': id(inconsistency),
            'recommended_category': recommended_category,
            'recommendation': f"Use '{recommended_category}' for all similar transactions",
            'reasoning': reasoning,
            'affected_transactions': inconsistency['group_size'],
            'confidence_improvement': self._calculate_confidence_improvement(
                inconsistency, recommended_category
            )
        }
    
    def _calculate_confidence_improvement(self, inconsistency: Dict[str, Any], 
                                        recommended_category: str) -> float:
        """
        Calculate potential confidence improvement from applying suggestion.
        
        Args:
            inconsistency: Inconsistency report
            recommended_category: Suggested category
            
        Returns:
            Estimated confidence improvement
        """
        current_confidences = []
        for cat_scores in inconsistency['confidence_scores'].values():
            current_confidences.extend(cat_scores)
        
        current_avg = sum(current_confidences) / len(current_confidences) if current_confidences else 0.0
        
        # Estimate new confidence based on pattern learning
        estimated_new_confidence = 0.85  # Conservative estimate for learned patterns
        
        return estimated_new_confidence - current_avg
    
    def apply_consistency_fix(self, suggestion: Dict[str, Any], 
                            transactions: List[Transaction]) -> Dict[str, Any]:
        """
        Apply a consistency fix by learning patterns from the suggestion.
        
        Args:
            suggestion: Suggestion from suggest_category_fixes
            transactions: Transactions to apply fix to
            
        Returns:
            Results of applying the fix
        """
        results = {
            'patterns_created': 0,
            'transactions_affected': 0,
            'errors': []
        }
        
        recommended_category = suggestion['recommended_category']
        
        try:
            # Learn patterns from transactions that should be in the recommended category
            for transaction in transactions:
                current_result = self.category_engine.categorize_transaction(transaction)
                
                if current_result.category != recommended_category:
                    # Learn from this transaction
                    self.learn_from_feedback(transaction, recommended_category, confidence=0.8)
                    results['patterns_created'] += 1
                    results['transactions_affected'] += 1
            
            self.logger.info(f"Applied consistency fix: {results['patterns_created']} patterns created for {results['transactions_affected']} transactions")
            
        except Exception as e:
            error_msg = f"Failed to apply consistency fix: {e}"
            results['errors'].append(error_msg)
            self.logger.error(error_msg)
        
        return results
    
    def batch_learn_from_historical_data(self, transactions: List[Transaction], 
                                       categories: Dict[str, str],
                                       confidence_threshold: float = 0.8) -> Dict[str, Any]:
        """
        Learn patterns from historical transaction data in batch.
        
        Args:
            transactions: List of transactions with known categories
            categories: Dictionary mapping transaction_id to category
            confidence_threshold: Minimum confidence for pattern creation
            
        Returns:
            Dictionary with learning results and statistics
        """
        results = {
            "processed": 0,
            "patterns_created": 0,
            "categories_learned": set(),
            "errors": []
        }
        
        try:
            for transaction in transactions:
                if transaction.transaction_id in categories:
                    category = categories[transaction.transaction_id]
                    
                    # Learn from this transaction
                    created_patterns = self.create_pattern_rule_from_manual_categorization(
                        transaction, category, user_confirmed=False
                    )
                    
                    results["processed"] += 1
                    results["patterns_created"] += len(created_patterns)
                    results["categories_learned"].add(category)
            
            results["categories_learned"] = list(results["categories_learned"])
            
            self.logger.info(f"Batch learning completed: {results['processed']} transactions, "
                           f"{results['patterns_created']} patterns created")
            
        except Exception as e:
            error_msg = f"Batch learning failed: {e}"
            results["errors"].append(error_msg)
            self.logger.error(error_msg)
        
        return results
    
    def analyze_and_fix_categorization_quality(self, transactions: List[Transaction],
                                             auto_fix: bool = False) -> Dict[str, Any]:
        """
        Analyze categorization quality and suggest or apply fixes.
        
        Args:
            transactions: List of transactions to analyze
            auto_fix: Whether to automatically apply suggested fixes
            
        Returns:
            Dictionary with analysis results and applied fixes
        """
        results = {
            "inconsistencies_found": 0,
            "suggestions_made": 0,
            "fixes_applied": 0,
            "quality_score": 0.0,
            "errors": []
        }
        
        try:
            # Detect inconsistencies
            inconsistencies = self.detect_inconsistencies(transactions)
            results["inconsistencies_found"] = len(inconsistencies)
            
            if inconsistencies:
                # Generate suggestions
                suggestions = self.suggest_category_fixes(inconsistencies)
                results["suggestions_made"] = len(suggestions)
                
                if auto_fix:
                    # Apply fixes automatically
                    for suggestion in suggestions:
                        # Find transactions for this inconsistency
                        inconsistency_transactions = []
                        for inconsistency in inconsistencies:
                            if id(inconsistency) == suggestion['inconsistency_id']:
                                inconsistency_transactions = inconsistency['transactions']
                                break
                        
                        if inconsistency_transactions:
                            fix_result = self.apply_consistency_fix(suggestion, inconsistency_transactions)
                            if not fix_result['errors']:
                                results["fixes_applied"] += 1
                            else:
                                results["errors"].extend(fix_result['errors'])
            
            # Calculate quality score
            results["quality_score"] = self._calculate_categorization_quality_score(transactions)
            
            self.logger.info(f"Quality analysis completed: {results['inconsistencies_found']} inconsistencies, "
                           f"quality score: {results['quality_score']:.2f}")
            
        except Exception as e:
            error_msg = f"Quality analysis failed: {e}"
            results["errors"].append(error_msg)
            self.logger.error(error_msg)
        
        return results
    
    def _calculate_categorization_quality_score(self, transactions: List[Transaction]) -> float:
        """
        Calculate overall categorization quality score.
        
        Args:
            transactions: List of transactions to analyze
            
        Returns:
            Quality score (0.0-1.0, higher is better)
        """
        if not transactions:
            return 0.0
        
        total_confidence = 0.0
        uncategorized_count = 0
        
        for transaction in transactions:
            result = self.category_engine.categorize_transaction(transaction)
            total_confidence += result.confidence
            
            if result.category in ["Uncategorized", "Unknown"]:
                uncategorized_count += 1
        
        # Average confidence score
        avg_confidence = total_confidence / len(transactions)
        
        # Penalty for uncategorized transactions
        uncategorized_penalty = uncategorized_count / len(transactions)
        
        # Quality score combines confidence and categorization coverage
        quality_score = avg_confidence * (1.0 - uncategorized_penalty * 0.5)
        
        return min(max(quality_score, 0.0), 1.0)
    
    def get_learning_stats(self) -> Dict[str, Any]:
        """Get learning and interaction statistics."""
        return self.learning_stats.copy()
    
    def reset_learning_stats(self) -> None:
        """Reset learning statistics."""
        self.learning_stats = {
            "manual_categorizations": 0,
            "patterns_learned": 0,
            "inconsistencies_detected": 0,
            "batch_reviews_completed": 0
        }
    
    def _create_new_category(self) -> Optional[str]:
        """
        Create a new category with user input.
        
        Returns:
            New category name if created, None if cancelled
        """
        while True:
            category_name = self.input_function("Enter new category name (or 'cancel'): ").strip()
            
            if category_name.lower() == 'cancel':
                return None
            
            if not category_name:
                self.print_function("Category name cannot be empty.")
                continue
            
            # Check if category already exists
            existing_categories = self.category_engine.get_available_categories()
            if category_name in existing_categories:
                self.print_function(f"Category '{category_name}' already exists.")
                continue
            
            # Confirm creation
            confirm = self.input_function(f"Create category '{category_name}'? (y/n): ").strip().lower()
            if confirm == 'y':
                self.logger.info(f"Created new category: {category_name}")
                return category_name
    
    def _extract_patterns(self, description: str) -> List[str]:
        """
        Extract meaningful patterns from transaction description.
        
        Args:
            description: Transaction description
            
        Returns:
            List of extracted patterns
        """
        patterns = []
        
        # Clean and normalize description
        cleaned = description.upper().strip()
        
        # Extract merchant name (first significant word/phrase)
        words = cleaned.split()
        if words:
            # Try to find the main merchant identifier
            for i, word in enumerate(words):
                # Skip common prefixes and suffixes
                if word in ['THE', 'A', 'AN', 'INC', 'LLC', 'CORP', 'CO', 'LTD']:
                    continue
                
                # Skip numbers and dates
                if word.isdigit() or '/' in word or '-' in word:
                    continue
                
                # Use the first meaningful word as a pattern
                if len(word) >= 3:
                    patterns.append(word)
                    break
            
            # Also try first two words if they form a meaningful merchant name
            if len(words) >= 2:
                first_two = ' '.join(words[:2])
                if len(first_two) >= 5 and not any(char.isdigit() for char in first_two):
                    patterns.append(first_two)
            
            # Extract domain-specific patterns
            domain_patterns = self._extract_domain_patterns(cleaned)
            patterns.extend(domain_patterns)
        
        # Remove duplicates while preserving order
        seen = set()
        unique_patterns = []
        for pattern in patterns:
            if pattern not in seen:
                seen.add(pattern)
                unique_patterns.append(pattern)
        
        return unique_patterns[:3]  # Limit to 3 patterns to avoid over-learning
    
    def _extract_domain_patterns(self, description: str) -> List[str]:
        """
        Extract domain-specific patterns from transaction description.
        
        Args:
            description: Cleaned transaction description
            
        Returns:
            List of domain-specific patterns
        """
        patterns = []
        
        # Common merchant patterns
        merchant_indicators = [
            ('STORE', 'SHOP', 'MARKET', 'MART'),
            ('GAS', 'FUEL', 'STATION'),
            ('RESTAURANT', 'CAFE', 'DINER', 'EATERY'),
            ('PHARMACY', 'DRUG', 'MEDICAL'),
            ('BANK', 'CREDIT', 'UNION'),
            ('HOTEL', 'MOTEL', 'INN'),
            ('AIRLINE', 'AIRWAYS', 'AIR')
        ]
        
        for indicator_group in merchant_indicators:
            for indicator in indicator_group:
                if indicator in description:
                    # Extract the word before the indicator if it exists
                    words = description.split()
                    for i, word in enumerate(words):
                        if word == indicator and i > 0:
                            prev_word = words[i-1]
                            if len(prev_word) >= 3 and not prev_word.isdigit():
                                patterns.append(f"{prev_word} {indicator}")
                    break
        
        # Extract patterns with numbers (like store numbers)
        import re
        store_pattern = re.findall(r'([A-Z]+)\s*#?\d+', description)
        for match in store_pattern:
            if len(match) >= 3:
                patterns.append(match)
        
        return patterns
    
    def create_pattern_rule_from_manual_categorization(self, transaction: Transaction, 
                                                     category: str, 
                                                     user_confirmed: bool = True) -> List[str]:
        """
        Create pattern rules from manual categorization with intelligent pattern selection.
        
        Args:
            transaction: Transaction that was manually categorized
            category: User-selected category
            user_confirmed: Whether user confirmed the pattern creation
            
        Returns:
            List of created pattern strings
        """
        created_patterns = []
        
        try:
            # Extract multiple pattern candidates
            pattern_candidates = self._extract_patterns(transaction.description)
            
            for pattern in pattern_candidates:
                # Determine confidence based on pattern specificity
                confidence = self._calculate_pattern_confidence(pattern, transaction.description)
                
                # Determine specificity level
                specificity = self._determine_pattern_specificity(pattern, transaction.description)
                
                # Add pattern rule to category engine
                self.category_engine.add_pattern_rule(
                    category=category,
                    pattern=pattern,
                    confidence=confidence,
                    specificity=specificity
                )
                
                created_patterns.append(pattern)
                self.learning_stats["patterns_learned"] += 1
                
                self.logger.info(f"Created pattern rule: '{pattern}' -> {category} "
                               f"(confidence: {confidence:.2f}, specificity: {specificity})")
        
        except Exception as e:
            self.logger.error(f"Failed to create pattern rule from manual categorization: {e}")
        
        return created_patterns
    
    def _calculate_pattern_confidence(self, pattern: str, description: str) -> float:
        """
        Calculate confidence score for a pattern based on its characteristics.
        
        Args:
            pattern: Pattern string
            description: Original transaction description
            
        Returns:
            Confidence score (0.0-1.0)
        """
        base_confidence = 0.85  # Base confidence for user feedback
        
        # Adjust based on pattern length (longer = more specific = higher confidence)
        length_bonus = min(len(pattern) / 20.0, 0.1)  # Up to 0.1 bonus
        
        # Adjust based on how much of the description the pattern covers
        coverage = len(pattern) / len(description) if description else 0
        coverage_bonus = min(coverage * 0.1, 0.05)  # Up to 0.05 bonus
        
        # Adjust based on pattern type
        if pattern.count(' ') > 0:  # Multi-word patterns are more specific
            multiword_bonus = 0.05
        else:
            multiword_bonus = 0.0
        
        final_confidence = min(base_confidence + length_bonus + coverage_bonus + multiword_bonus, 1.0)
        return final_confidence
    
    def _determine_pattern_specificity(self, pattern: str, description: str) -> str:
        """
        Determine specificity level for a pattern.
        
        Args:
            pattern: Pattern string
            description: Original transaction description
            
        Returns:
            Specificity level: "low", "medium", "high", "very_high"
        """
        # Very high specificity: pattern covers most of the description
        coverage = len(pattern) / len(description) if description else 0
        if coverage > 0.7:
            return "very_high"
        
        # High specificity: multi-word patterns or long single words
        if pattern.count(' ') > 0 or len(pattern) > 10:
            return "high"
        
        # Medium specificity: moderate length single words
        if len(pattern) >= 5:
            return "medium"
        
        # Low specificity: short patterns
        return "low"
    
    def _group_similar_transactions(self, transactions: List[Transaction], 
                                  threshold: float) -> List[List[Transaction]]:
        """
        Group similar transactions based on description similarity.
        
        Args:
            transactions: List of transactions to group
            threshold: Similarity threshold (0.0-1.0)
            
        Returns:
            List of transaction groups
        """
        groups = []
        
        for transaction in transactions:
            # Find existing group with similar transactions
            added_to_group = False
            
            for group in groups:
                # Check similarity with first transaction in group
                if self._calculate_similarity(transaction.description, group[0].description) >= threshold:
                    group.append(transaction)
                    added_to_group = True
                    break
            
            # Create new group if no similar group found
            if not added_to_group:
                groups.append([transaction])
        
        return groups
    
    def _calculate_similarity(self, desc1: str, desc2: str) -> float:
        """
        Calculate similarity between two transaction descriptions.
        
        Args:
            desc1: First description
            desc2: Second description
            
        Returns:
            Similarity score (0.0-1.0)
        """
        # Simple word-based similarity
        words1 = set(desc1.upper().split())
        words2 = set(desc2.upper().split())
        
        if not words1 and not words2:
            return 1.0
        
        if not words1 or not words2:
            return 0.0
        
        # Jaccard similarity
        intersection = len(words1.intersection(words2))
        union = len(words1.union(words2))
        
        return intersection / union if union > 0 else 0.0