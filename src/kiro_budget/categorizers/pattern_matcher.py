"""
Pattern-based transaction categorization using merchant name patterns.
"""

import re
from typing import List, Optional, Dict
from .interfaces import PatternMatcherInterface
from .models import CategoryMatch, PatternRule


class PatternMatcher(PatternMatcherInterface):
    """
    Pattern-based categorizer that matches transaction descriptions against
    predefined patterns with specificity scoring and conflict resolution.
    """
    
    def __init__(self):
        """Initialize the pattern matcher with empty pattern storage."""
        self._patterns: Dict[str, List[PatternRule]] = {}
        self._specificity_weights = {
            "low": 1,
            "medium": 2, 
            "high": 3,
            "very_high": 4
        }
    
    def match_patterns(self, description: str) -> Optional[CategoryMatch]:
        """
        Find the best matching pattern for a transaction description.
        
        Args:
            description: Transaction description to match
            
        Returns:
            Best CategoryMatch if found, None otherwise
        """
        if not description:
            return None
            
        all_matches = self.get_matching_patterns(description)
        if not all_matches:
            return None
            
        # Return the match with highest combined score (confidence + specificity)
        return max(all_matches, key=self._calculate_match_score)
    
    def get_matching_patterns(self, description: str) -> List[CategoryMatch]:
        """
        Get all patterns that match a description.
        
        Args:
            description: Transaction description
            
        Returns:
            List of all matching CategoryMatch objects
        """
        matches = []
        
        for category, patterns in self._patterns.items():
            for pattern_rule in patterns:
                if self._pattern_matches(description, pattern_rule):
                    match = CategoryMatch(
                        category=category,
                        pattern=pattern_rule.pattern,
                        confidence=pattern_rule.confidence,
                        match_type=pattern_rule.type,
                        specificity=pattern_rule.specificity
                    )
                    matches.append(match)
        
        return matches
    
    def add_pattern(self, category: str, pattern: str, confidence: float, 
                   specificity: str = "medium") -> None:
        """
        Add a new pattern rule.
        
        Args:
            category: Category name
            pattern: Pattern string
            confidence: Confidence score (0.0-1.0)
            specificity: Pattern specificity level
        """
        if category not in self._patterns:
            self._patterns[category] = []
            
        # Determine pattern type based on content
        pattern_type = self._determine_pattern_type(pattern)
        
        pattern_rule = PatternRule(
            pattern=pattern,
            confidence=confidence,
            type=pattern_type,
            specificity=specificity,
            case_sensitive=False
        )
        
        self._patterns[category].append(pattern_rule)
    
    def load_patterns_from_dict(self, patterns_dict: Dict[str, List[Dict]]) -> None:
        """
        Load patterns from a dictionary structure (typically from YAML/JSON).
        
        Args:
            patterns_dict: Dictionary with category -> list of pattern configs
        """
        self._patterns.clear()
        
        for category, pattern_configs in patterns_dict.items():
            for config in pattern_configs:
                self.add_pattern(
                    category=category,
                    pattern=config["pattern"],
                    confidence=config.get("confidence", 0.8),
                    specificity=config.get("specificity", "medium")
                )
    
    def resolve_pattern_conflicts(self, matches: List[CategoryMatch]) -> CategoryMatch:
        """
        Resolve conflicts when multiple patterns match by prioritizing specificity and confidence.
        
        Args:
            matches: List of CategoryMatch objects that all match
            
        Returns:
            The best CategoryMatch based on specificity and confidence
        """
        if not matches:
            raise ValueError("Cannot resolve conflicts with empty matches list")
        
        if len(matches) == 1:
            return matches[0]
        
        # Sort by combined score (specificity + confidence)
        return max(matches, key=self._calculate_match_score)
    
    def get_categories(self) -> List[str]:
        """Get list of all configured categories."""
        return list(self._patterns.keys())
    
    def get_patterns_for_category(self, category: str) -> List[PatternRule]:
        """Get all patterns for a specific category."""
        return self._patterns.get(category, [])
    
    def _pattern_matches(self, description: str, pattern_rule: PatternRule) -> bool:
        """
        Check if a pattern rule matches a description.
        
        Args:
            description: Transaction description
            pattern_rule: Pattern rule to test
            
        Returns:
            True if pattern matches, False otherwise
        """
        # Normalize text by treating hyphens as spaces for better matching
        def normalize_text(text: str) -> str:
            return text.replace('-', ' ')
        
        # Normalize both description and pattern
        normalized_desc = normalize_text(description)
        normalized_pattern = normalize_text(pattern_rule.pattern)
        
        # Apply case sensitivity
        if not pattern_rule.case_sensitive:
            normalized_desc = normalized_desc.upper()
            normalized_pattern = normalized_pattern.upper()
        
        try:
            if pattern_rule.type == "exact":
                return normalized_desc == normalized_pattern
            elif pattern_rule.type == "substring":
                return normalized_pattern in normalized_desc
            elif pattern_rule.type == "regex":
                flags = 0 if pattern_rule.case_sensitive else re.IGNORECASE
                # For regex, normalize the description but use original pattern
                return bool(re.search(pattern_rule.pattern, normalized_desc, flags))
            else:
                # Default to substring matching
                return normalized_pattern in normalized_desc
        except re.error:
            # If regex is invalid, fall back to substring matching
            return normalized_pattern in normalized_desc
    
    def _determine_pattern_type(self, pattern: str) -> str:
        """
        Automatically determine pattern type based on content.
        
        Args:
            pattern: Pattern string
            
        Returns:
            Pattern type: "regex", "substring", or "exact"
        """
        # Check for common regex metacharacters
        regex_chars = set(".*+?^${}[]|()")
        if any(char in pattern for char in regex_chars):
            return "regex"
        
        # Default to substring matching
        return "substring"
    
    def _calculate_match_score(self, match: CategoryMatch) -> float:
        """
        Calculate combined score for a match based on confidence and specificity.
        
        Args:
            match: CategoryMatch to score
            
        Returns:
            Combined score for ranking matches
        """
        specificity_weight = self._specificity_weights.get(match.specificity, 2)
        
        # Combine confidence (0.0-1.0) with specificity weight (1-4)
        # Normalize specificity to 0.0-1.0 range and weight it
        specificity_score = (specificity_weight - 1) / 3  # Maps 1-4 to 0.0-1.0
        
        # Add pattern length bonus for more specific patterns
        pattern_length_bonus = min(len(match.pattern) / 50.0, 0.2)  # Up to 0.2 bonus
        
        # Weight confidence most heavily, then specificity, then pattern length
        return (0.6 * match.confidence) + (0.3 * specificity_score) + (0.1 * pattern_length_bonus)
    
    def calculate_specificity_score(self, pattern: str, description: str) -> float:
        """
        Calculate how specific a pattern is for a given description.
        
        Args:
            pattern: Pattern string
            description: Transaction description
            
        Returns:
            Specificity score (higher = more specific)
        """
        if not pattern or not description:
            return 0.0
        
        # Normalize text by treating hyphens as spaces for better matching
        def normalize_text(text: str) -> str:
            return text.replace('-', ' ')
        
        normalized_pattern = normalize_text(pattern).upper()
        normalized_description = normalize_text(description).upper()
            
        # Longer patterns are generally more specific
        pattern_length_score = min(len(normalized_pattern) / 20.0, 1.0)  # Normalize to 0-1
        
        # Exact matches are most specific
        if normalized_pattern == normalized_description:
            return 1.0
            
        # Patterns that match a larger portion of the description are more specific
        if normalized_pattern in normalized_description:
            coverage_score = len(normalized_pattern) / len(normalized_description)
            return min(pattern_length_score + coverage_score, 1.0)
            
        return pattern_length_score