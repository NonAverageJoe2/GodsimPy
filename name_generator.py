"""
Comprehensive Name Generation System

A modular, extensible system for generating unique names for various game entities.
Supports countries, cultures, religions, and can be easily extended for future needs.
"""

import random
import re
from typing import List, Dict, Set, Optional, Tuple
from enum import Enum
from dataclasses import dataclass


class NameType(Enum):
    """Types of names that can be generated."""
    COUNTRY = "country"
    CULTURE = "culture"
    RELIGION = "religion"
    CITY = "city"
    PERSON_MALE = "person_male"
    PERSON_FEMALE = "person_female"
    DYNASTY = "dynasty"
    ARTIFACT = "artifact"
    ORGANIZATION = "organization"


@dataclass
class LanguagePattern:
    """Defines phonetic patterns for generating names in different linguistic styles."""
    name: str
    consonants: List[str]
    vowels: List[str]
    syllable_patterns: List[str]  # V = vowel, C = consonant
    prefixes: List[str] = None
    suffixes: List[str] = None
    forbidden_sequences: List[str] = None  # Sequences to avoid
    min_syllables: int = 2
    max_syllables: int = 4
    
    def __post_init__(self):
        if self.prefixes is None:
            self.prefixes = []
        if self.suffixes is None:
            self.suffixes = []
        if self.forbidden_sequences is None:
            self.forbidden_sequences = []


class NameGenerator:
    """
    Advanced name generation system with linguistic patterns and uniqueness tracking.
    """
    
    def __init__(self, seed: Optional[int] = None):
        self.rng = random.Random(seed)
        self.generated_names: Dict[NameType, Set[str]] = {nt: set() for nt in NameType}
        self.language_patterns = self._initialize_language_patterns()
        self.name_templates = self._initialize_name_templates()
        
    def _initialize_language_patterns(self) -> Dict[str, LanguagePattern]:
        """Initialize various linguistic patterns for name generation."""
        patterns = {}
        
        # Latin/Roman inspired
        patterns["latin"] = LanguagePattern(
            name="Latin",
            consonants=["b", "c", "d", "f", "g", "h", "l", "m", "n", "p", "r", "s", "t", "v", "x", "z"],
            vowels=["a", "e", "i", "o", "u"],
            syllable_patterns=["CV", "CVC", "V", "VC"],
            suffixes=["ia", "us", "um", "ius", "ensis", "anum"],
            forbidden_sequences=["xx", "zz", "hh"],
            min_syllables=2,
            max_syllables=4
        )
        
        # Germanic inspired
        patterns["germanic"] = LanguagePattern(
            name="Germanic",
            consonants=["b", "d", "f", "g", "h", "k", "l", "m", "n", "r", "s", "t", "w", "z", "th", "ch", "sch"],
            vowels=["a", "e", "i", "o", "u", "ae", "ie"],
            syllable_patterns=["CV", "CVC", "CVCC", "CCV"],
            suffixes=["berg", "heim", "land", "burg", "wald", "hausen"],
            prefixes=["von", "zur", "der"],
            forbidden_sequences=["hh", "ww"],
            min_syllables=2,
            max_syllables=3
        )
        
        # Celtic inspired
        patterns["celtic"] = LanguagePattern(
            name="Celtic",
            consonants=["b", "c", "d", "f", "g", "l", "m", "n", "r", "s", "t", "w", "th", "ch", "gh"],
            vowels=["a", "e", "i", "o", "u", "ae", "ei", "ou"],
            syllable_patterns=["CV", "CVC", "V", "CCV"],
            suffixes=["ach", "agh", "ain", "ead", "ean"],
            prefixes=["mac", "o'", "fitz"],
            forbidden_sequences=["chch", "thth"],
            min_syllables=2,
            max_syllables=4
        )
        
        # Slavic inspired  
        patterns["slavic"] = LanguagePattern(
            name="Slavic",
            consonants=["b", "c", "d", "g", "k", "l", "m", "n", "p", "r", "s", "t", "v", "z", "zh", "ch", "sh"],
            vowels=["a", "e", "i", "o", "u", "y"],
            syllable_patterns=["CV", "CVC", "CCV", "CCVC"],
            suffixes=["ova", "ova", "ska", "sky", "grad", "burg"],
            prefixes=["novo", "staro"],
            forbidden_sequences=["zhzh", "shsh"],
            min_syllables=2,
            max_syllables=4
        )
        
        # Arabic inspired
        patterns["arabic"] = LanguagePattern(
            name="Arabic",
            consonants=["b", "d", "f", "g", "h", "j", "k", "l", "m", "n", "r", "s", "t", "w", "z", "sh", "kh", "th"],
            vowels=["a", "e", "i", "o", "u"],
            syllable_patterns=["CV", "CVC", "CVCC"],
            prefixes=["al-", "abd-", "ibn-"],
            suffixes=["an", "iya", "stan"],
            forbidden_sequences=["hh"],
            min_syllables=2,
            max_syllables=4
        )
        
        # East Asian inspired
        patterns["sinitic"] = LanguagePattern(
            name="Sinitic",
            consonants=["b", "d", "f", "g", "h", "j", "k", "l", "m", "n", "p", "r", "s", "t", "w", "x", "z", "zh", "ch", "sh"],
            vowels=["a", "e", "i", "o", "u", "ao", "ai", "ei", "ou"],
            syllable_patterns=["CV", "CVC"],
            forbidden_sequences=["xx", "zhzh"],
            min_syllables=1,
            max_syllables=3
        )
        
        # Greek inspired
        patterns["greek"] = LanguagePattern(
            name="Greek",
            consonants=["b", "d", "f", "g", "k", "l", "m", "n", "p", "r", "s", "t", "th", "ph", "ch"],
            vowels=["a", "e", "i", "o", "u", "ai", "ei", "ou"],
            syllable_patterns=["CV", "CVC", "CCV"],
            suffixes=["os", "es", "ia", "ikos", "tes"],
            forbidden_sequences=["hh", "phph"],
            min_syllables=2,
            max_syllables=4
        )
        
        # Romance (Italian/Spanish/French inspired)
        patterns["romance"] = LanguagePattern(
            name="Romance",
            consonants=["b", "c", "d", "f", "g", "l", "m", "n", "p", "r", "s", "t", "v", "z"],
            vowels=["a", "e", "i", "o", "u"],
            syllable_patterns=["CV", "CVC", "CCV"],
            suffixes=["ia", "ina", "ese", "ano", "ero"],
            prefixes=["san", "monte", "valle"],
            forbidden_sequences=["zz"],
            min_syllables=2,
            max_syllables=4
        )
        
        # Norse/Scandinavian inspired  
        patterns["norse"] = LanguagePattern(
            name="Norse",
            consonants=["b", "d", "f", "g", "h", "j", "k", "l", "m", "n", "r", "s", "t", "v"],
            vowels=["a", "e", "i", "o", "u", "ae", "oe"],
            syllable_patterns=["CV", "CVC", "CCV"],
            suffixes=["sen", "son", "dottir", "stad", "borg", "vik"],
            prefixes=["bjorn", "erik", "thor"],
            forbidden_sequences=["jj"],
            min_syllables=2,
            max_syllables=3
        )
        
        # Turkish/Turkic inspired
        patterns["turkic"] = LanguagePattern(
            name="Turkic", 
            consonants=["b", "c", "d", "f", "g", "h", "k", "l", "m", "n", "p", "r", "s", "t", "y", "z"],
            vowels=["a", "e", "i", "o", "u"],
            syllable_patterns=["CV", "CVC"],
            suffixes=["li", "ci", "oglu", "bay", "han"],
            forbidden_sequences=["hh"],
            min_syllables=2,
            max_syllables=3
        )
        
        # Persian inspired
        patterns["persian"] = LanguagePattern(
            name="Persian",
            consonants=["b", "d", "f", "g", "h", "j", "k", "l", "m", "n", "r", "s", "t", "v", "z", "sh", "kh"],
            vowels=["a", "e", "i", "o", "u"],
            syllable_patterns=["CV", "CVC", "CCV"],
            suffixes=["an", "abad", "shahr", "stan"],
            prefixes=["shah", "mir"],
            forbidden_sequences=["hh"],
            min_syllables=2,
            max_syllables=4
        )
        
        # Fantasy/Mystical patterns (DISABLED BY DEFAULT - kept for future use)
        # patterns["elvish"] = LanguagePattern(
        #     name="Elvish",
        #     consonants=["l", "n", "r", "s", "t", "th", "f", "m", "d", "g", "v"],
        #     vowels=["a", "e", "i", "o", "u", "ae", "ea", "ie", "ai"],
        #     syllable_patterns=["CV", "CVC", "V", "CCV"],
        #     suffixes=["iel", "ael", "oth", "eth", "rim", "dor"],
        #     prefixes=["el", "gal", "cel"],
        #     forbidden_sequences=["th", "dd", "ll"],
        #     min_syllables=2,
        #     max_syllables=5
        # )
        # 
        # patterns["dwarven"] = LanguagePattern(
        #     name="Dwarven",
        #     consonants=["b", "d", "f", "g", "k", "m", "n", "r", "t", "th", "gr", "br", "dr"],
        #     vowels=["a", "e", "i", "o", "u"],
        #     syllable_patterns=["CVC", "CVCC", "CCV"],
        #     suffixes=["in", "ur", "im", "ak", "ek"],
        #     forbidden_sequences=["uu", "ii"],
        #     min_syllables=2,
        #     max_syllables=3
        # )
        
        return patterns
    
    def _initialize_name_templates(self) -> Dict[NameType, Dict[str, List[str]]]:
        """Initialize templates for different name types."""
        templates = {}
        
        # Country name templates
        templates[NameType.COUNTRY] = {
            "descriptive": [
                "{adjective} {noun}",
                "{noun} of {noun}",
                "{noun}land", 
                "{noun}burg",
                "{noun}heim",
                "United {noun}",
                "Free {noun}",
                "{noun} Republic",
                "{noun} Empire",
                "{noun} Kingdom"
            ],
            "geographic": [
                "North {noun}",
                "South {noun}",
                "East {noun}",
                "West {noun}",
                "Upper {noun}",
                "Lower {noun}",
                "Great {noun}",
                "New {noun}"
            ]
        }
        
        # Culture name templates (real-world inspired)
        templates[NameType.CULTURE] = {
            "geographic": [
                "{place}ans",      # Romans, Germans
                "{place}ese",      # Chinese, Japanese  
                "{place}ish",      # Spanish, Turkish
                "{place}ic",       # Nordic, Slavic
                "{place}ian",      # Persian, Italian
                "People of {place}",
                "{place} People"
            ],
            "tribal": [
                "{noun} Folk",
                "{noun} Peoples", 
                "{noun} Clans",
                "Sons of {noun}",
                "Daughters of {noun}",
                "{noun} Tribes"
            ]
        }
        
        # Religion name templates
        templates[NameType.RELIGION] = {
            "deity_based": [
                "Worship of {deity}",
                "{deity}ism",
                "Faith of {deity}",
                "Church of {deity}",
                "Order of {deity}",
                "Brotherhood of {deity}",
                "Temple of {deity}"
            ],
            "concept_based": [
                "The {concept} Path",
                "Followers of {concept}",
                "{concept} Faith",
                "The {concept} Way",
                "Order of {concept}",
                "Church of {concept}"
            ],
            "mystical": [
                "The {mystical} Circle",
                "{mystical} Mysteries", 
                "The {mystical} Covenant",
                "{mystical} Enlightenment"
            ]
        }
        
        return templates
    
    def generate_syllable(self, pattern: LanguagePattern, syllable_type: str) -> str:
        """Generate a single syllable based on pattern."""
        syllable = ""
        
        for char_type in syllable_type:
            if char_type == 'C':
                syllable += self.rng.choice(pattern.consonants)
            elif char_type == 'V':
                syllable += self.rng.choice(pattern.vowels)
                
        return syllable
    
    def generate_base_name(self, pattern: LanguagePattern) -> str:
        """Generate a base name using linguistic patterns."""
        syllable_count = self.rng.randint(pattern.min_syllables, pattern.max_syllables)
        syllables = []
        
        for i in range(syllable_count):
            syllable_pattern = self.rng.choice(pattern.syllable_patterns)
            syllable = self.generate_syllable(pattern, syllable_pattern)
            syllables.append(syllable)
        
        name = "".join(syllables)
        
        # Apply prefix/suffix
        if pattern.prefixes and self.rng.random() < 0.3:
            name = self.rng.choice(pattern.prefixes) + name
        
        if pattern.suffixes and self.rng.random() < 0.4:
            name = name + self.rng.choice(pattern.suffixes)
        
        # Check for forbidden sequences
        for forbidden in pattern.forbidden_sequences:
            if forbidden in name:
                # Try again with different approach
                return self.generate_base_name(pattern)
        
        return name.capitalize()
    
    def generate_template_name(self, name_type: NameType, template_category: str = None) -> str:
        """Generate name using templates with placeholder substitution."""
        if name_type not in self.name_templates:
            raise ValueError(f"No templates defined for {name_type}")
        
        templates = self.name_templates[name_type]
        
        if template_category and template_category in templates:
            template = self.rng.choice(templates[template_category])
        else:
            # Choose random category
            category = self.rng.choice(list(templates.keys()))
            template = self.rng.choice(templates[category])
        
        # Generate substitutions for placeholders
        substitutions = self._generate_substitutions(template)
        
        # Apply substitutions
        name = template
        for placeholder, replacement in substitutions.items():
            name = name.replace(f"{{{placeholder}}}", replacement)
        
        return name
    
    def _generate_substitutions(self, template: str) -> Dict[str, str]:
        """Generate substitutions for template placeholders."""
        substitutions = {}
        
        # Find all placeholders
        placeholders = re.findall(r'\{(\w+)\}', template)
        
        for placeholder in placeholders:
            if placeholder == "noun":
                substitutions[placeholder] = self._generate_noun()
            elif placeholder == "adjective":
                substitutions[placeholder] = self._generate_adjective()
            elif placeholder == "deity":
                substitutions[placeholder] = self._generate_deity_name()
            elif placeholder == "concept":
                substitutions[placeholder] = self._generate_concept()
            elif placeholder == "mystical":
                substitutions[placeholder] = self._generate_mystical_term()
            elif placeholder == "place":
                substitutions[placeholder] = self._generate_place_name()
        
        return substitutions
    
    def _generate_noun(self) -> str:
        """Generate base nouns for name construction."""
        natural_features = ["River", "Mountain", "Valley", "Forest", "Lake", "Hill", "Stone", "Tree", "Wind", "Sun", "Moon", "Star", "Fire", "Water", "Earth", "Sky"]
        animals = ["Wolf", "Eagle", "Bear", "Lion", "Dragon", "Tiger", "Hawk", "Raven", "Fox", "Stag", "Bull", "Serpent"]
        concepts = ["Honor", "Glory", "Victory", "Peace", "Strength", "Wisdom", "Light", "Shadow", "Dawn", "Storm", "Flame", "Steel"]
        
        categories = [natural_features, animals, concepts]
        category = self.rng.choice(categories)
        return self.rng.choice(category)
    
    def _generate_adjective(self) -> str:
        """Generate descriptive adjectives."""
        adjectives = ["Noble", "Ancient", "Golden", "Silver", "Crimson", "Sacred", "Eternal", "Mighty", "Grand", "Royal", "Divine", "Mystical", "Hidden", "Forgotten", "Lost", "New", "Old"]
        return self.rng.choice(adjectives)
    
    def _generate_deity_name(self) -> str:
        """Generate deity names using various patterns."""
        pattern_name = self.rng.choice(["latin", "celtic", "greek", "arabic"])
        pattern = self.language_patterns[pattern_name]
        return self.generate_base_name(pattern)
    
    def _generate_concept(self) -> str:
        """Generate abstract concepts for religions."""
        concepts = ["Light", "Truth", "Balance", "Harmony", "Unity", "Wisdom", "Eternity", "Purity", "Justice", "Redemption", "Enlightenment", "Transcendence"]
        return self.rng.choice(concepts)
    
    def _generate_mystical_term(self) -> str:
        """Generate mystical terms."""
        mystical = ["Sacred", "Divine", "Eternal", "Celestial", "Astral", "Mystic", "Arcane", "Ancient", "Hidden", "Secret", "Forbidden", "Lost"]
        return self.rng.choice(mystical)
    
    def _generate_place_name(self) -> str:
        """Generate place names for template substitution."""
        # Use a random linguistic pattern to generate a base place name
        pattern_name = self.rng.choice(list(self.language_patterns.keys()))
        pattern = self.language_patterns[pattern_name]
        return self.generate_base_name(pattern)
    
    def generate_unique_name(self, name_type: NameType, max_attempts: int = 100, **kwargs) -> str:
        """
        Generate a unique name that hasn't been used before for this type.
        
        Args:
            name_type: Type of name to generate
            max_attempts: Maximum attempts before giving up on uniqueness
            **kwargs: Additional parameters like pattern_name, template_category
        """
        for attempt in range(max_attempts):
            # Choose generation method
            if self.rng.random() < 0.6 and name_type in self.name_templates:
                # Use template-based generation
                name = self.generate_template_name(name_type, kwargs.get('template_category'))
            else:
                # Use pattern-based generation
                pattern_name = kwargs.get('pattern_name')
                if pattern_name is None:
                    pattern_name = self.rng.choice(list(self.language_patterns.keys()))
                pattern = self.language_patterns[pattern_name]
                name = self.generate_base_name(pattern)
            
            # Check uniqueness
            if name not in self.generated_names[name_type]:
                self.generated_names[name_type].add(name)
                return name
        
        # If we can't generate unique name, add suffix
        base_name = name
        counter = 1
        while name in self.generated_names[name_type]:
            name = f"{base_name} {counter}"
            counter += 1
        
        self.generated_names[name_type].add(name)
        return name
    
    def generate_country_name(self, style: str = None) -> str:
        """Generate a country name with optional style preference."""
        return self.generate_unique_name(
            NameType.COUNTRY, 
            template_category=style,
            pattern_name=style
        )
    
    def generate_culture_name(self, style: str = None) -> str:
        """Generate a culture name with optional style preference."""
        return self.generate_unique_name(
            NameType.CULTURE,
            template_category=style,
            pattern_name=style
        )
    
    def generate_religion_name(self, style: str = None) -> str:
        """Generate a religion name with optional style preference."""
        return self.generate_unique_name(
            NameType.RELIGION,
            template_category=style,
            pattern_name=style
        )
    
    def generate_city_name(self, style: str = None) -> str:
        """Generate a city name."""
        return self.generate_unique_name(
            NameType.CITY,
            pattern_name=style or self.rng.choice(list(self.language_patterns.keys()))
        )
    
    def generate_person_name(self, gender: str = "male", style: str = None) -> str:
        """Generate a person name."""
        name_type = NameType.PERSON_MALE if gender == "male" else NameType.PERSON_FEMALE
        return self.generate_unique_name(
            name_type,
            pattern_name=style or self.rng.choice(list(self.language_patterns.keys()))
        )
    
    def reset_used_names(self, name_type: Optional[NameType] = None):
        """Reset the used names tracking."""
        if name_type:
            self.generated_names[name_type].clear()
        else:
            for nt in NameType:
                self.generated_names[nt].clear()
    
    def get_usage_stats(self) -> Dict[NameType, int]:
        """Get statistics on name usage."""
        return {nt: len(names) for nt, names in self.generated_names.items()}
    
    def get_available_linguistic_types(self) -> List[str]:
        """Get list of available linguistic pattern names."""
        return list(self.language_patterns.keys())
    
    def assign_linguistic_type_to_culture(self, culture_id: int, seed: Optional[int] = None) -> str:
        """Assign a linguistic type to a culture based on weighted probabilities."""
        # Use culture_id as seed modifier for deterministic assignment
        local_rng = random.Random((seed or 0) + culture_id * 1000)
        
        # Weight real-world linguistic types more heavily
        real_world_patterns = ["latin", "germanic", "celtic", "slavic", "arabic", "sinitic", "greek", "romance", "norse", "turkic", "persian"]
        
        # Weighted selection - favor diversity but with some patterns more common
        weights = {
            "latin": 1.5,      # Classical/Romance base
            "germanic": 1.3,   # Germanic languages  
            "celtic": 1.0,     # Celtic languages
            "slavic": 1.2,     # Slavic languages
            "arabic": 1.1,     # Semitic languages
            "sinitic": 1.0,    # East Asian languages
            "greek": 0.8,      # Greek/Hellenic
            "romance": 1.4,    # Romance languages
            "norse": 0.9,      # Scandinavian
            "turkic": 0.7,     # Turkic languages
            "persian": 0.6     # Iranian languages
        }
        
        # Create weighted list for selection
        weighted_patterns = []
        for pattern in real_world_patterns:
            weight = weights.get(pattern, 1.0)
            weighted_patterns.extend([pattern] * int(weight * 10))
        
        return local_rng.choice(weighted_patterns)
    
    def generate_culture_with_linguistic_type(self, linguistic_type: str) -> Tuple[str, str]:
        """Generate a culture name with specific linguistic type."""
        if linguistic_type not in self.language_patterns:
            raise ValueError(f"Unknown linguistic type: {linguistic_type}")
        
        culture_name = self.generate_unique_name(NameType.CULTURE, pattern_name=linguistic_type)
        return culture_name, linguistic_type


# Convenience functions for easy integration
def create_name_generator(seed: Optional[int] = None) -> NameGenerator:
    """Create a new name generator instance."""
    return NameGenerator(seed)


def generate_country_names(count: int, seed: Optional[int] = None) -> List[str]:
    """Generate multiple unique country names."""
    generator = NameGenerator(seed)
    return [generator.generate_country_name() for _ in range(count)]


def generate_culture_names(count: int, seed: Optional[int] = None) -> List[str]:
    """Generate multiple unique culture names."""
    generator = NameGenerator(seed)
    return [generator.generate_culture_name() for _ in range(count)]


def generate_religion_names(count: int, seed: Optional[int] = None) -> List[str]:
    """Generate multiple unique religion names."""
    generator = NameGenerator(seed)
    return [generator.generate_religion_name() for _ in range(count)]


# Example usage and testing
if __name__ == "__main__":
    # Test the name generator
    generator = NameGenerator(seed=42)
    
    print("=== Country Names ===")
    for _ in range(10):
        print(f"- {generator.generate_country_name()}")
    
    print("\n=== Culture Names ===")
    for _ in range(10):
        print(f"- {generator.generate_culture_name()}")
    
    print("\n=== Religion Names ===")  
    for _ in range(10):
        print(f"- {generator.generate_religion_name()}")
    
    print("\n=== City Names ===")
    for _ in range(10):
        print(f"- {generator.generate_city_name()}")
    
    print("\n=== Person Names ===")
    for _ in range(5):
        print(f"- {generator.generate_person_name('male')}")
    for _ in range(5):
        print(f"- {generator.generate_person_name('female')}")
    
    print(f"\nUsage Stats: {generator.get_usage_stats()}")