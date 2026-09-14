"""
Cognicare Gameplay Services.
Provides modular game engine implementations and session lifecycle helpers.
Phase 5: Gameplay Foundation + Memory Market.
"""

import random
from decimal import Decimal
from django.core.exceptions import ValidationError
from django.utils import timezone
from apps.accounts.models import Role
from apps.games.models import Game, GameSession, GameRound


# Catalog of relatable everyday market items.
# Designed for high legibility, clean visual badges, and complete independence from emoji.
MARKET_ITEMS_CATALOG = {
    'apples': {
        'id': 'apples',
        'name': 'Fresh Apples',
        'short_name': 'Apples',
        'category': 'Fruit',
        'descriptor': 'Crisp and sweet',
    },
    'milk': {
        'id': 'milk',
        'name': 'Fresh Milk',
        'short_name': 'Milk',
        'category': 'Dairy',
        'descriptor': 'Bottle of fresh milk',
    },
    'bread': {
        'id': 'bread',
        'name': 'Whole Wheat Bread',
        'short_name': 'Bread',
        'category': 'Bakery',
        'descriptor': 'Freshly baked loaf',
    },
    'tea': {
        'id': 'tea',
        'name': 'Tea Leaves',
        'short_name': 'Tea',
        'category': 'Pantry',
        'descriptor': 'Aromatic Assam tea',
    },
    'rice': {
        'id': 'rice',
        'name': 'Basmati Rice',
        'short_name': 'Rice',
        'category': 'Pantry',
        'descriptor': 'Bag of long-grain rice',
    },
    'honey': {
        'id': 'honey',
        'name': 'Pure Honey',
        'short_name': 'Honey',
        'category': 'Pantry',
        'descriptor': 'Jar of golden honey',
    },
    'carrots': {
        'id': 'carrots',
        'name': 'Garden Carrots',
        'short_name': 'Carrots',
        'category': 'Vegetables',
        'descriptor': 'Crunchy orange carrots',
    },
    'bananas': {
        'id': 'bananas',
        'name': 'Ripe Bananas',
        'short_name': 'Bananas',
        'category': 'Fruit',
        'descriptor': 'Bunch of sweet bananas',
    },
    'potatoes': {
        'id': 'potatoes',
        'name': 'Farm Potatoes',
        'short_name': 'Potatoes',
        'category': 'Vegetables',
        'descriptor': 'Fresh russet potatoes',
    },
    'flowers': {
        'id': 'flowers',
        'name': 'Fresh Marigolds',
        'short_name': 'Flowers',
        'category': 'Garden',
        'descriptor': 'Bright fragrant blossoms',
    },
    'oranges': {
        'id': 'oranges',
        'name': 'Sweet Oranges',
        'short_name': 'Oranges',
        'category': 'Fruit',
        'descriptor': 'Juicy citrus oranges',
    },
    'spinach': {
        'id': 'spinach',
        'name': 'Green Spinach',
        'short_name': 'Spinach',
        'category': 'Vegetables',
        'descriptor': 'Fresh tender greens',
    },
}


class MemoryMarketEngine:
    """
    Game Engine for Memory Market (Working/Short-Term Memory).
    Supports deterministic multi-round configuration and server-side validation.
    """
    SLUG = 'memory-market'
    TOTAL_ROUNDS = 3

    # Deterministic round configurations for prototype:
    # Round 1: 3 targets, 3 distractors (6 total options)
    # Round 2: 4 targets, 4 distractors (8 total options)
    # Round 3: 4 targets, 4 distractors (8 total options)
    ROUND_CONFIGS = {
        1: {
            'target_ids': ['apples', 'milk', 'bread'],
            'distractor_ids': ['tea', 'carrots', 'bananas'],
        },
        2: {
            'target_ids': ['tea', 'honey', 'rice', 'bananas'],
            'distractor_ids': ['apples', 'potatoes', 'milk', 'flowers'],
        },
        3: {
            'target_ids': ['carrots', 'potatoes', 'flowers', 'oranges'],
            'distractor_ids': ['spinach', 'bread', 'rice', 'honey'],
        },
    }

    @classmethod
    def get_round_data(cls, round_number, session=None):
        """
        Retrieves the structured stimulus data for a given round.
        Returns a dict with targets and market_options.
        """
        if round_number not in cls.ROUND_CONFIGS:
            raise ValueError(f"Invalid round number {round_number}. Max rounds is {cls.TOTAL_ROUNDS}.")

        config = cls.ROUND_CONFIGS[round_number]
        target_items = [MARKET_ITEMS_CATALOG[item_id] for item_id in config['target_ids']]
        distractor_items = [MARKET_ITEMS_CATALOG[item_id] for item_id in config['distractor_ids']]

        # Combined sorted/predictable market choices for selection stage
        all_market_items = target_items + distractor_items
        # Sort alphabetically by short_name for a neat, stable shelf presentation
        all_market_items = sorted(all_market_items, key=lambda x: x['short_name'])

        return {
            'round_number': round_number,
            'total_rounds': cls.TOTAL_ROUNDS,
            'target_items': target_items,
            'market_items': all_market_items,
            'target_ids': config['target_ids'],
        }

    @classmethod
    def evaluate_round(cls, round_number, actual_selected_ids, response_time_ms, session=None):
        """
        Evaluates the member's submitted item selections against expected targets.
        Calculates correct items, mistakes, and generates gentle feedback.
        """
        if round_number not in cls.ROUND_CONFIGS:
            raise ValueError(f"Invalid round number {round_number}.")

        config = cls.ROUND_CONFIGS[round_number]
        expected_ids = set(config['target_ids'])
        actual_ids = set(actual_selected_ids)

        correct_picks = actual_ids.intersection(expected_ids)
        distractor_picks = actual_ids.difference(expected_ids)
        missed_targets = expected_ids.difference(actual_ids)

        is_all_correct = (actual_ids == expected_ids)
        mistake_count = len(distractor_picks) + len(missed_targets)
        score_for_round = len(correct_picks)
        max_score_for_round = len(expected_ids)

        # Gentle, reassuring feedback messages (non-clinical, supportive)
        if is_all_correct:
            feedback_message = "Wonderful! You remembered all items on your list."
            feedback_tone = "success"
        elif len(correct_picks) > 0:
            feedback_message = f"Good effort! You remembered {len(correct_picks)} out of {max_score_for_round} items."
            feedback_tone = "encouraging"
        else:
            feedback_message = "Thank you for trying. Let's continue together to the next round."
            feedback_tone = "neutral"

        return {
            'is_correct': is_all_correct,
            'score': score_for_round,
            'max_score': max_score_for_round,
            'mistake_count': mistake_count,
            'correct_ids': list(correct_picks),
            'distractor_ids': list(distractor_picks),
            'missed_ids': list(missed_targets),
            'feedback_message': feedback_message,
            'feedback_tone': feedback_tone,
        }

    @classmethod
    def get_instructions(cls):
        """
        Elder-friendly step-by-step instructions for the game introduction screen.
        """
        return [
            {
                'number': 1,
                'title': "Look & Remember",
                'description': "You will see a small grocery list of everyday items. Take all the time you need to read and memorize them.",
            },
            {
                'number': 2,
                'title': 'Click "I Am Ready"',
                'description': "There is no timer or hurry. When you feel confident you remember the items, click the ready button.",
            },
            {
                'number': 3,
                'title': "Pick Your Items",
                'description': "Tap or click the items you remember from the market shelf. You can tap again to uncheck any item.",
            },
            {
                'number': 4,
                'title': "Receive Gentle Feedback",
                'description': "Click \"Check My Items\" to review your picks. You will complete 3 short rounds.",
            },
        ]


class DailyLifeJourneyEngine:
    """
    Game Engine for Daily Life Journey (Executive Function & Procedural Memory Sequencing).
    Presents familiar everyday routines and validates ordered step placement.
    """
    SLUG = 'daily-life-journey'
    TOTAL_ROUNDS = 3
    TEMPLATE_NAME = 'games/daily_life_journey.html'

    # Deterministic round configurations:
    # Round 1: Making Tea (3 steps)
    # Round 2: Morning Walk (4 steps)
    # Round 3: Handwashing (4 steps)
    ROUND_CONFIGS = {
        1: {
            'scenario_title': "Making a Morning Cup of Tea",
            'scenario_instruction': "Arrange the steps to prepare a warm cup of morning tea.",
            'target_ids': ['tea_boil', 'tea_leaves', 'tea_steep'],
            'steps': [
                {
                    'id': 'tea_boil',
                    'title': 'Boil Fresh Water',
                    'description': 'Fill the kettle and bring clean water to a gentle boil.',
                },
                {
                    'id': 'tea_leaves',
                    'title': 'Add Tea Leaves',
                    'description': 'Place aromatic tea leaves or a tea bag into your cup or teapot.',
                },
                {
                    'id': 'tea_steep',
                    'title': 'Pour & Steep',
                    'description': 'Pour the boiling water over the tea and allow it to steep for a few minutes.',
                },
            ],
            'shuffled_ids': ['tea_steep', 'tea_boil', 'tea_leaves'],
        },
        2: {
            'scenario_title': "Preparing for a Morning Walk",
            'scenario_instruction': "Arrange the steps in natural order before heading out for your walk.",
            'target_ids': ['walk_weather', 'walk_shoes', 'walk_keys', 'walk_door'],
            'steps': [
                {
                    'id': 'walk_weather',
                    'title': 'Check the Weather',
                    'description': 'Look outside the window to see the sunshine and temperature.',
                },
                {
                    'id': 'walk_shoes',
                    'title': 'Put On Walking Shoes',
                    'description': 'Tie on comfortable, supportive walking shoes for a secure stroll.',
                },
                {
                    'id': 'walk_keys',
                    'title': 'Take House Keys & Water',
                    'description': 'Gather your keys and a small bottle of water in your pocket.',
                },
                {
                    'id': 'walk_door',
                    'title': 'Step Outside & Lock Door',
                    'description': 'Gently close and lock the front door as you head out.',
                },
            ],
            'shuffled_ids': ['walk_door', 'walk_weather', 'walk_shoes', 'walk_keys'],
        },
        3: {
            'scenario_title': "Washing Hands Before a Meal",
            'scenario_instruction': "Arrange the everyday steps for washing your hands properly.",
            'target_ids': ['wash_water', 'wash_soap', 'wash_rinse', 'wash_dry'],
            'steps': [
                {
                    'id': 'wash_water',
                    'title': 'Turn On Water & Wet Hands',
                    'description': 'Open the tap and thoroughly wet your hands with clean water.',
                },
                {
                    'id': 'wash_soap',
                    'title': 'Apply Gentle Soap',
                    'description': 'Dispense soap and rub hands together to make a warm lather for 20 seconds.',
                },
                {
                    'id': 'wash_rinse',
                    'title': 'Rinse Thoroughly',
                    'description': 'Hold hands under running water until all soap washes cleanly away.',
                },
                {
                    'id': 'wash_dry',
                    'title': 'Dry with a Clean Towel',
                    'description': 'Pat your hands gently with a soft, clean towel.',
                },
            ],
            'shuffled_ids': ['wash_rinse', 'wash_dry', 'wash_water', 'wash_soap'],
        },
    }

    @classmethod
    def get_instructions(cls):
        """
        Elder-friendly step-by-step instructions for the game introduction screen.
        """
        return [
            {
                'number': 1,
                'title': "Read the Daily Story",
                'description': "You will see a familiar daily routine, such as making morning tea or preparing for a stroll.",
            },
            {
                'number': 2,
                'title': "Choose the Next Step",
                'description': "Tap each step in the order it happens naturally from start to finish.",
            },
            {
                'number': 3,
                'title': "Adjust Your Order Anytime",
                'description': "Tap any step in your tray to remove it, or use Undo to adjust your sequence.",
            },
            {
                'number': 4,
                'title': "Check Your Sequence",
                'description': "When you feel satisfied with the sequence, tap Check My Sequence to continue.",
            },
        ]

    @classmethod
    def get_round_data(cls, round_number, session=None):
        """
        Retrieves the structured stimulus data for a given round.
        Returns a dict with scenario title, instruction, available steps, and target IDs.
        """
        if round_number not in cls.ROUND_CONFIGS:
            raise ValueError(f"Invalid round number {round_number}. Max rounds is {cls.TOTAL_ROUNDS}.")

        config = cls.ROUND_CONFIGS[round_number]
        steps_by_id = {s['id']: s for s in config['steps']}
        available_steps = [steps_by_id[s_id] for s_id in config['shuffled_ids']]

        return {
            'round_number': round_number,
            'total_rounds': cls.TOTAL_ROUNDS,
            'scenario_title': config['scenario_title'],
            'scenario_instruction': config['scenario_instruction'],
            'available_steps': available_steps,
            'target_ids': config['target_ids'],
        }

    @classmethod
    def evaluate_round(cls, round_number, actual_selected_ids, response_time_ms, session=None):
        """
        Evaluates the member's submitted step sequence against expected order.
        Scores 1 point per correctly placed position.
        """
        if round_number not in cls.ROUND_CONFIGS:
            raise ValueError(f"Invalid round number {round_number}.")

        config = cls.ROUND_CONFIGS[round_number]
        expected_ids = config['target_ids']
        max_score_for_round = len(expected_ids)

        # Positional evaluation:
        # A step receives 1 point if actual_selected_ids[i] == expected_ids[i]
        correct_ids = []
        misplaced_ids = []

        for idx, step_id in enumerate(actual_selected_ids):
            if idx < len(expected_ids) and step_id == expected_ids[idx]:
                correct_ids.append(step_id)
            else:
                misplaced_ids.append(step_id)

        is_all_correct = (actual_selected_ids == expected_ids)
        score_for_round = len(correct_ids)
        mistake_count = len(misplaced_ids) + max(0, len(expected_ids) - len(actual_selected_ids))

        # Gentle, reassuring feedback messages
        if is_all_correct:
            feedback_message = "Wonderful! You placed every step in the perfect order."
            feedback_tone = "success"
        elif score_for_round > 0:
            feedback_message = f"Good effort! You placed {score_for_round} out of {max_score_for_round} steps in order."
            feedback_tone = "encouraging"
        else:
            feedback_message = "Thank you for arranging the steps. Let's continue together to the next journey."
            feedback_tone = "neutral"

        return {
            'is_correct': is_all_correct,
            'score': score_for_round,
            'max_score': max_score_for_round,
            'mistake_count': mistake_count,
            'correct_ids': correct_ids,
            'misplaced_ids': misplaced_ids,
            'distractor_ids': [],
            'missed_ids': [],
            'expected_ids': expected_ids,
            'feedback_message': feedback_message,
            'feedback_tone': feedback_tone,
        }


class FamiliarFacesEngine:
    """
    Game Engine for Familiar Faces (Facial Recognition, Relational & Episodic Memory).
    Presents real photos of the member's family and friends curated by their caregiver.
    3 rounds:
      - Round 1: 3 choices (1 target, 2 distractors)
      - Round 2: 4 choices (1 target, 3 distractors)
      - Round 3: 4 choices (1 target, 3 distractors)
    """
    SLUG = 'familiar-faces'
    TOTAL_ROUNDS = 3
    TOTAL_MAX_SCORE = 3
    MIN_PEOPLE_REQUIRED = 4
    TEMPLATE_NAME = 'games/familiar_faces.html'

    ROUND_CHOICE_COUNTS = {
        1: 3,
        2: 4,
        3: 4,
    }

    @classmethod
    def get_instructions(cls):
        """
        Elder-friendly step-by-step instructions for the game introduction screen.
        """
        return [
            {
                'number': 1,
                'title': "Look at the Photo",
                'description': "You will see a photograph of someone close to you—a family member, grandchild, or dear friend.",
            },
            {
                'number': 2,
                'title': "Take All the Time You Need",
                'description': "There are no timers. Look at the friendly face and take a moment to recall memories together.",
            },
            {
                'number': 3,
                'title': "Select Who It Is",
                'description': "Choose the matching name and relationship from the options below the picture.",
            },
            {
                'number': 4,
                'title': "Enjoy the Connection",
                'description': "Receive warm, encouraging feedback as you complete 3 pleasant rounds.",
            },
        ]

    @classmethod
    def get_active_people_for_session(cls, session):
        """
        Fetches the pool of active familiar people with photos for the session's member.
        Sorted deterministically by ID.
        """
        if not session or not session.member:
            return []
        return list(
            session.member.familiar_people
            .filter(is_active=True)
            .exclude(photo='')
            .order_by('id')
        )

    @classmethod
    def get_session_plan(cls, session):
        """
        Deterministically plans the 3 rounds for a session using the session ID as seed.
        Ensures 3 distinct targets across the 3 rounds.
        """
        people = cls.get_active_people_for_session(session)
        if len(people) < cls.MIN_PEOPLE_REQUIRED:
            raise ValueError(
                f"Familiar Faces requires at least {cls.MIN_PEOPLE_REQUIRED} active people with photos. Currently found {len(people)}."
            )

        rng_session = random.Random(session.id)
        target_people = rng_session.sample(people, cls.TOTAL_ROUNDS)

        plan = {}
        for r_num in range(1, cls.TOTAL_ROUNDS + 1):
            target = target_people[r_num - 1]
            distractor_candidates = [p for p in people if p.id != target.id]
            needed_distractors = cls.ROUND_CHOICE_COUNTS[r_num] - 1

            rng_round = random.Random(session.id * 100 + r_num)
            distractors = rng_round.sample(distractor_candidates, needed_distractors)

            choices = [target] + distractors
            rng_round.shuffle(choices)

            plan[r_num] = {
                'target': target,
                'distractors': distractors,
                'choices': choices,
            }
        return plan

    @classmethod
    def get_round_data(cls, round_number, session=None):
        if round_number not in cls.ROUND_CHOICE_COUNTS:
            raise ValueError(f"Invalid round number {round_number}. Max rounds is {cls.TOTAL_ROUNDS}.")

        if not session:
            raise ValueError("FamiliarFacesEngine requires an active GameSession.")

        plan = cls.get_session_plan(session)
        round_plan = plan[round_number]
        target = round_plan['target']
        choices = round_plan['choices']

        return {
            'round_number': round_number,
            'total_rounds': cls.TOTAL_ROUNDS,
            'prompt_text': "Who is this familiar person?",
            'target_photo_url': target.photo.url if target.photo else '',
            'target_name': target.name,
            'target_relationship': target.relationship,
            'target_ids': [str(target.id)],
            'choices': [
                {
                    'id': str(p.id),
                    'name': p.name,
                    'relationship': p.relationship,
                }
                for p in choices
            ],
        }

    @classmethod
    def evaluate_round(cls, round_number, actual_selected_ids, response_time_ms, session=None):
        if round_number not in cls.ROUND_CHOICE_COUNTS:
            raise ValueError(f"Invalid round number {round_number}.")

        if not session:
            raise ValueError("FamiliarFacesEngine requires an active GameSession.")

        round_data = cls.get_round_data(round_number, session=session)
        target_id = round_data['target_ids'][0]
        target_name = round_data['target_name']
        target_relationship = round_data['target_relationship']

        norm_selected = [str(x) for x in actual_selected_ids]
        is_correct = (len(norm_selected) == 1 and norm_selected[0] == target_id)

        if is_correct:
            correct_ids = [target_id]
            distractor_ids = []
            missed_ids = []
            mistake_count = 0
            score = 1
            if target_relationship:
                feedback_message = f"Wonderful! That is your {target_relationship.lower()}, {target_name}."
            else:
                feedback_message = f"Wonderful! That is {target_name}."
            feedback_tone = "success"
        else:
            correct_ids = []
            distractor_ids = norm_selected
            missed_ids = [target_id]
            mistake_count = 1
            score = 0
            if target_relationship:
                feedback_message = f"That is your {target_relationship.lower()}, {target_name}. Thank you for looking at this memory together."
            else:
                feedback_message = f"That is {target_name}. Thank you for looking at this memory together."
            feedback_tone = "encouraging"

        return {
            'is_correct': is_correct,
            'score': score,
            'max_score': 1,
            'mistake_count': mistake_count,
            'correct_ids': correct_ids,
            'distractor_ids': distractor_ids,
            'missed_ids': missed_ids,
            'misplaced_ids': [],
            'target_name': target_name,
            'target_relationship': target_relationship,
            'feedback_message': feedback_message,
            'feedback_tone': feedback_tone,
        }



FOCUS_FINDER_CATALOG = {
    'marigold': {
        'id': 'marigold',
        'name': 'Golden Marigold',
        'category': 'Flowers',
        'color_theme': 'Amber Gold',
        'svg_icon': '''<svg viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Golden Marigold">
  <circle cx="32" cy="32" r="22" fill="#FEF3C7" stroke="#D97706" stroke-width="2"/>
  <circle cx="32" cy="32" r="15" fill="#FDE68A" stroke="#B45309" stroke-width="2"/>
  <circle cx="32" cy="32" r="8" fill="#F59E0B" stroke="#92400E" stroke-width="2"/>
  <path d="M32 10V4M32 60V54M10 32H4M60 32H54M16 16L12 12M52 52L48 48M16 48L12 52M52 16L48 20" stroke="#F59E0B" stroke-width="3" stroke-linecap="round"/>
</svg>''',
    },
    'rose': {
        'id': 'rose',
        'name': 'Red Rose',
        'category': 'Flowers',
        'color_theme': 'Crimson Red',
        'svg_icon': '''<svg viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Red Rose">
  <path d="M32 38C40 38 46 32 46 24C46 16 38 12 32 16C26 12 18 16 18 24C18 32 24 38 32 38Z" fill="#FEE2E2" stroke="#DC2626" stroke-width="2.5"/>
  <path d="M32 20C36 18 39 21 38 25C37 28 34 30 32 30C30 30 27 28 26 25C25 21 28 18 32 20Z" fill="#EF4444" stroke="#B91C1C" stroke-width="2"/>
  <path d="M32 38V56M32 46C26 44 22 48 20 52M32 48C38 46 42 50 44 54" stroke="#059669" stroke-width="2.5" stroke-linecap="round"/>
</svg>''',
    },
    'tulip': {
        'id': 'tulip',
        'name': 'Pink Tulip',
        'category': 'Flowers',
        'color_theme': 'Soft Pink',
        'svg_icon': '''<svg viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Pink Tulip">
  <path d="M32 12C36 18 38 28 32 38C26 28 28 18 32 12Z" fill="#F43F5E" stroke="#BE123C" stroke-width="2"/>
  <path d="M22 18C22 28 26 36 32 38C28 34 20 28 22 18Z" fill="#FDA4AF" stroke="#BE123C" stroke-width="2"/>
  <path d="M42 18C42 28 38 36 32 38C36 34 44 28 42 18Z" fill="#FDA4AF" stroke="#BE123C" stroke-width="2"/>
  <path d="M32 38V56M32 48C38 46 44 40 46 34M32 50C26 48 20 42 18 36" stroke="#10B981" stroke-width="2.5" stroke-linecap="round"/>
</svg>''',
    },
    'sunflower': {
        'id': 'sunflower',
        'name': 'Bright Sunflower',
        'category': 'Flowers',
        'color_theme': 'Golden Yellow',
        'svg_icon': '''<svg viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Bright Sunflower">
  <circle cx="32" cy="32" r="13" fill="#78350F" stroke="#451A03" stroke-width="2"/>
  <circle cx="32" cy="32" r="8" fill="#92400E" stroke="#B45309" stroke-width="1.5" stroke-dasharray="2 2"/>
  <path d="M32 6L35 15L44 11L41 20L50 20L44 27L52 32L44 37L50 44L41 44L44 53L35 49L32 58L29 49L20 53L23 44L14 44L20 37L12 32L20 27L14 20L23 20L20 11L29 15L32 6Z" fill="#FBBF24" stroke="#D97706" stroke-width="1.5"/>
</svg>''',
    },
    'daisy': {
        'id': 'daisy',
        'name': 'White Daisy',
        'category': 'Flowers',
        'color_theme': 'White Gold',
        'svg_icon': '''<svg viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="White Daisy">
  <ellipse cx="32" cy="14" rx="5" ry="10" fill="#F8FAFC" stroke="#64748B" stroke-width="1.5"/>
  <ellipse cx="32" cy="50" rx="5" ry="10" fill="#F8FAFC" stroke="#64748B" stroke-width="1.5"/>
  <ellipse cx="14" cy="32" rx="10" ry="5" fill="#F8FAFC" stroke="#64748B" stroke-width="1.5"/>
  <ellipse cx="50" cy="32" rx="10" ry="5" fill="#F8FAFC" stroke="#64748B" stroke-width="1.5"/>
  <ellipse cx="19" cy="19" rx="6" ry="9" transform="rotate(-45 19 19)" fill="#F8FAFC" stroke="#64748B" stroke-width="1.5"/>
  <ellipse cx="45" cy="45" rx="6" ry="9" transform="rotate(-45 45 45)" fill="#F8FAFC" stroke="#64748B" stroke-width="1.5"/>
  <ellipse cx="45" cy="19" rx="6" ry="9" transform="rotate(45 45 19)" fill="#F8FAFC" stroke="#64748B" stroke-width="1.5"/>
  <ellipse cx="19" cy="45" rx="6" ry="9" transform="rotate(45 19 45)" fill="#F8FAFC" stroke="#64748B" stroke-width="1.5"/>
  <circle cx="32" cy="32" r="9" fill="#F59E0B" stroke="#B45309" stroke-width="2"/>
</svg>''',
    },
    'bluebell': {
        'id': 'bluebell',
        'name': 'Gentle Bluebell',
        'category': 'Flowers',
        'color_theme': 'Sky Blue',
        'svg_icon': '''<svg viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Gentle Bluebell">
  <path d="M18 56C20 40 28 26 44 14" stroke="#059669" stroke-width="2.5" stroke-linecap="round"/>
  <path d="M38 18C44 18 52 26 48 36C45 38 41 36 38 34C35 36 31 38 28 36C24 26 32 18 38 18Z" fill="#BAE6FD" stroke="#0284C7" stroke-width="2"/>
  <path d="M28 36L26 42M38 34V42M48 36L50 42" stroke="#0284C7" stroke-width="1.5" stroke-linecap="round"/>
</svg>''',
    },
    'oak_leaf': {
        'id': 'oak_leaf',
        'name': 'Green Oak Leaf',
        'category': 'Foliage & Botanicals',
        'color_theme': 'Forest Green',
        'svg_icon': '''<svg viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Green Oak Leaf">
  <path d="M32 8C35 12 40 12 41 16C42 20 38 22 42 26C46 30 45 34 40 38C42 42 38 46 34 48V56H30V48C26 46 22 42 24 38C19 34 18 30 22 26C26 22 22 20 23 16C24 12 29 12 32 8Z" fill="#DCFCE7" stroke="#16A34A" stroke-width="2.5"/>
  <path d="M32 14V48M32 24L38 20M32 28L26 24M32 34L39 31M32 38L25 35" stroke="#15803D" stroke-width="2" stroke-linecap="round"/>
</svg>''',
    },
    'maple_leaf': {
        'id': 'maple_leaf',
        'name': 'Orange Maple Leaf',
        'category': 'Foliage & Botanicals',
        'color_theme': 'Warm Orange',
        'svg_icon': '''<svg viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Orange Maple Leaf">
  <path d="M32 6L36 18L44 14L42 24L52 26L44 34L48 44L36 40L34 56H30L28 40L16 44L20 34L12 26L22 24L20 14L28 18L32 6Z" fill="#FFEDD5" stroke="#EA580C" stroke-width="2.5"/>
  <path d="M32 14V42M32 26L42 20M32 26L22 20M32 34L44 32M32 34L20 32" stroke="#C2410C" stroke-width="2" stroke-linecap="round"/>
</svg>''',
    },
    'clover': {
        'id': 'clover',
        'name': 'Four-Leaf Clover',
        'category': 'Foliage & Botanicals',
        'color_theme': 'Emerald Green',
        'svg_icon': '''<svg viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Four-Leaf Clover">
  <path d="M32 30C28 20 22 20 22 26C22 30 28 32 32 32C28 36 22 38 22 42C22 48 28 48 32 38C36 48 42 48 42 42C42 38 36 36 32 32C36 32 42 30 42 26C42 20 36 20 32 30Z" fill="#BBF7D0" stroke="#059669" stroke-width="2.5"/>
  <path d="M32 35C30 44 26 52 18 56" stroke="#047857" stroke-width="2.5" stroke-linecap="round"/>
</svg>''',
    },
    'pinecone': {
        'id': 'pinecone',
        'name': 'Brown Pinecone',
        'category': 'Foliage & Botanicals',
        'color_theme': 'Cedar Brown',
        'svg_icon': '''<svg viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Brown Pinecone">
  <path d="M32 8C24 16 18 28 18 40C18 50 24 56 32 56C40 56 46 50 46 40C46 28 40 16 32 8Z" fill="#EFE8E1" stroke="#78350F" stroke-width="2"/>
  <path d="M22 26C28 28 36 28 42 26M20 34C28 37 36 37 44 34M20 42C28 45 36 45 44 42M24 50C28 52 36 52 40 50M32 8V56" stroke="#92400E" stroke-width="2" stroke-linecap="round"/>
</svg>''',
    },
    'acorn': {
        'id': 'acorn',
        'name': 'Forest Acorn',
        'category': 'Foliage & Botanicals',
        'color_theme': 'Warm Chestnut',
        'svg_icon': '''<svg viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Forest Acorn">
  <path d="M32 8V16M32 8C34 6 38 6 40 8" stroke="#451A03" stroke-width="2.5" stroke-linecap="round"/>
  <path d="M16 22C16 16 23 16 32 16C41 16 48 16 48 22C48 26 44 28 32 28C20 28 16 26 16 22Z" fill="#D97706" stroke="#78350F" stroke-width="2"/>
  <path d="M18 26C18 36 22 52 32 56C42 52 46 36 46 26" fill="#FDE68A" stroke="#B45309" stroke-width="2.5"/>
</svg>''',
    },
    'teacup': {
        'id': 'teacup',
        'name': 'Warm Teacup',
        'category': 'Kitchen & Table',
        'color_theme': 'Calm Teal',
        'svg_icon': '''<svg viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Warm Teacup">
  <path d="M14 26H46V38C46 46 38 50 30 50C22 50 14 46 14 38V26Z" fill="#CCFBF1" stroke="#0D9488" stroke-width="2.5"/>
  <path d="M46 30H52C55 30 57 32 57 35C57 38 55 40 52 40H45" stroke="#0D9488" stroke-width="2.5" stroke-linecap="round"/>
  <path d="M10 54H50" stroke="#0F766E" stroke-width="2.5" stroke-linecap="round"/>
  <path d="M24 18C23 14 26 12 25 8M34 18C33 14 36 12 35 8" stroke="#14B8A6" stroke-width="2" stroke-linecap="round"/>
</svg>''',
    },
    'teapot': {
        'id': 'teapot',
        'name': 'Ceramic Teapot',
        'category': 'Kitchen & Table',
        'color_theme': 'Classic Navy',
        'svg_icon': '''<svg viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Ceramic Teapot">
  <path d="M18 32C18 24 24 20 32 20C40 20 46 24 46 32C46 44 40 48 32 48C24 48 18 44 18 32Z" fill="#E0F2FE" stroke="#0369A1" stroke-width="2.5"/>
  <path d="M26 20C26 16 28 14 32 14C36 14 38 16 38 20" fill="#BAE6FD" stroke="#0369A1" stroke-width="2"/>
  <circle cx="32" cy="12" r="2.5" fill="#0284C7"/>
  <path d="M46 28C52 28 56 32 54 38C52 42 46 40 45 38" stroke="#0369A1" stroke-width="2.5" stroke-linecap="round"/>
  <path d="M18 34L10 28V24L18 28" fill="#BAE6FD" stroke="#0369A1" stroke-width="2" stroke-linejoin="round"/>
</svg>''',
    },
    'pitcher': {
        'id': 'pitcher',
        'name': 'Water Pitcher',
        'category': 'Kitchen & Table',
        'color_theme': 'Warm Terracotta',
        'svg_icon': '''<svg viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Water Pitcher">
  <path d="M24 16L18 22H42L38 16H24Z" fill="#FFEDD5" stroke="#C2410C" stroke-width="2"/>
  <path d="M20 22L16 46C16 52 22 56 30 56C38 56 44 52 44 46L40 22" fill="#FED7AA" stroke="#C2410C" stroke-width="2.5"/>
  <path d="M41 26H48C52 26 54 30 52 38C50 44 44 46 42 46" stroke="#C2410C" stroke-width="2.5" stroke-linecap="round"/>
</svg>''',
    },
    'apple': {
        'id': 'apple',
        'name': 'Crisp Red Apple',
        'category': 'Kitchen & Table',
        'color_theme': 'Bright Red',
        'svg_icon': '''<svg viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Crisp Red Apple">
  <path d="M32 14C24 14 16 20 16 32C16 46 24 54 32 54C40 54 48 46 48 32C48 20 40 14 32 14Z" fill="#FEE2E2" stroke="#DC2626" stroke-width="2.5"/>
  <path d="M32 8C33 12 33 14 32 17" stroke="#78350F" stroke-width="2.5" stroke-linecap="round"/>
  <path d="M33 11C38 9 43 11 44 14C40 16 35 14 33 11Z" fill="#86EFAC" stroke="#16A34A" stroke-width="1.5"/>
</svg>''',
    },
    'pear': {
        'id': 'pear',
        'name': 'Sweet Green Pear',
        'category': 'Kitchen & Table',
        'color_theme': 'Olive Green',
        'svg_icon': '''<svg viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Sweet Green Pear">
  <path d="M32 16C26 16 24 24 20 32C16 40 16 52 32 54C48 52 48 40 44 32C40 24 38 16 32 16Z" fill="#DCFCE7" stroke="#15803D" stroke-width="2.5"/>
  <path d="M32 8C33 11 34 13 32 16" stroke="#78350F" stroke-width="2.5" stroke-linecap="round"/>
  <path d="M33 11C37 9 41 11 42 14C38 15 35 13 33 11Z" fill="#86EFAC" stroke="#15803D" stroke-width="1.5"/>
</svg>''',
    },
    'honey_jar': {
        'id': 'honey_jar',
        'name': 'Golden Honey Jar',
        'category': 'Kitchen & Table',
        'color_theme': 'Honey Amber',
        'svg_icon': '''<svg viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Golden Honey Jar">
  <path d="M22 16H42V20H22V16Z" fill="#FDE68A" stroke="#B45309" stroke-width="2"/>
  <path d="M20 20C16 26 16 48 20 52C24 56 40 56 44 52C48 48 48 26 44 20H20Z" fill="#FEF3C7" stroke="#D97706" stroke-width="2.5"/>
  <rect x="24" y="30" width="16" height="14" rx="2" fill="#FDE68A" stroke="#B45309" stroke-width="1.5"/>
  <line x1="28" y1="35" x2="36" y2="35" stroke="#92400E" stroke-width="1.5" stroke-linecap="round"/>
  <line x1="28" y1="39" x2="34" y2="39" stroke="#92400E" stroke-width="1.5" stroke-linecap="round"/>
</svg>''',
    },
    'brass_key': {
        'id': 'brass_key',
        'name': 'Antique Brass Key',
        'category': 'Keepsakes',
        'color_theme': 'Antique Gold',
        'svg_icon': '''<svg viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Antique Brass Key">
  <circle cx="22" cy="24" r="10" fill="#FEF3C7" stroke="#B45309" stroke-width="2.5"/>
  <circle cx="22" cy="24" r="4" fill="#FFFFFF" stroke="#B45309" stroke-width="1.5"/>
  <path d="M29 31L48 50M42 44L47 39M46 48L51 43" stroke="#B45309" stroke-width="3" stroke-linecap="round"/>
</svg>''',
    },
    'pocket_watch': {
        'id': 'pocket_watch',
        'name': 'Pocket Watch',
        'category': 'Keepsakes',
        'color_theme': 'Antique Silver',
        'svg_icon': '''<svg viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Pocket Watch">
  <circle cx="32" cy="36" r="20" fill="#F8FAFC" stroke="#475569" stroke-width="2.5"/>
  <circle cx="32" cy="36" r="15" fill="#FFFFFF" stroke="#94A3B8" stroke-width="1.5"/>
  <path d="M32 36V26M32 36L39 36" stroke="#1E293B" stroke-width="2" stroke-linecap="round"/>
  <path d="M30 16H34V12H30V16ZM32 12V8" stroke="#475569" stroke-width="2" stroke-linecap="round"/>
</svg>''',
    },
    'lantern': {
        'id': 'lantern',
        'name': 'Garden Lantern',
        'category': 'Keepsakes',
        'color_theme': 'Bronze Amber',
        'svg_icon': '''<svg viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Garden Lantern">
  <path d="M24 16C24 10 40 10 40 16" stroke="#78350F" stroke-width="2.5" stroke-linecap="round"/>
  <path d="M22 20L26 16H38L42 20H22Z" fill="#FEF3C7" stroke="#78350F" stroke-width="2"/>
  <path d="M22 20L20 46H44L42 20H22Z" fill="#FFFBEB" stroke="#92400E" stroke-width="2.5"/>
  <circle cx="32" cy="34" r="6" fill="#F59E0B" stroke="#D97706" stroke-width="1.5"/>
  <rect x="18" y="46" width="28" height="6" rx="2" fill="#D97706" stroke="#78350F" stroke-width="2"/>
</svg>''',
    },
    'hand_bell': {
        'id': 'hand_bell',
        'name': 'Brass Hand Bell',
        'category': 'Keepsakes',
        'color_theme': 'Warm Brass',
        'svg_icon': '''<svg viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Brass Hand Bell">
  <path d="M32 6V20" stroke="#78350F" stroke-width="3" stroke-linecap="round"/>
  <path d="M32 20C24 20 20 32 18 44H46C44 32 40 20 32 20Z" fill="#FEF3C7" stroke="#B45309" stroke-width="2.5"/>
  <path d="M14 44H50C51 44 52 46 51 48H13C12 46 13 44 14 44Z" fill="#FDE68A" stroke="#B45309" stroke-width="2"/>
  <circle cx="32" cy="52" r="3" fill="#92400E"/>
</svg>''',
    },
    'quill': {
        'id': 'quill',
        'name': 'Writing Quill',
        'category': 'Keepsakes',
        'color_theme': 'Plum Purple',
        'svg_icon': '''<svg viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Writing Quill">
  <path d="M48 10C34 16 26 28 18 48L14 54L20 50C28 42 36 34 50 20C54 16 52 10 48 10Z" fill="#F3E8FF" stroke="#7E22CE" stroke-width="2"/>
  <path d="M14 54L18 48M28 36L34 40M34 30L40 34" stroke="#6B21A8" stroke-width="1.5" stroke-linecap="round"/>
</svg>''',
    },
    'compass': {
        'id': 'compass',
        'name': 'Pocket Compass',
        'category': 'Keepsakes',
        'color_theme': 'Deep Indigo',
        'svg_icon': '''<svg viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Pocket Compass">
  <circle cx="32" cy="32" r="22" fill="#EEF2FF" stroke="#3730A3" stroke-width="2.5"/>
  <circle cx="32" cy="32" r="17" fill="#FFFFFF" stroke="#818CF8" stroke-width="1.5"/>
  <polygon points="32,18 36,32 32,30 28,32" fill="#DC2626" stroke="#991B1B" stroke-width="1"/>
  <polygon points="32,46 36,32 32,34 28,32" fill="#475569" stroke="#1E293B" stroke-width="1"/>
  <circle cx="32" cy="32" r="2" fill="#1E293B"/>
</svg>''',
    },
    'magnifier': {
        'id': 'magnifier',
        'name': 'Reading Glass',
        'category': 'Keepsakes',
        'color_theme': 'Pewter Slate',
        'svg_icon': '''<svg viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Reading Glass">
  <circle cx="26" cy="26" r="16" fill="#F0FDFA" stroke="#0F766E" stroke-width="3"/>
  <circle cx="26" cy="26" r="12" fill="#CCFBF1" stroke="#5EEAD4" stroke-width="1.5"/>
  <path d="M38 38L52 52" stroke="#78350F" stroke-width="5" stroke-linecap="round"/>
  <path d="M21 21C23 18 27 18 29 19" stroke="#FFFFFF" stroke-width="2" stroke-linecap="round"/>
</svg>''',
    },
}


class FocusFinderEngine:
    """
    Game Engine for Focus Finder (Visual Selective Attention).
    Elder-friendly visual search with deterministic grid configurations
    and feature-conjunction distractors across 5 difficulty levels.
    """
    SLUG = 'focus-finder'
    TOTAL_ROUNDS = 3
    TOTAL_MAX_SCORE = 3
    TEMPLATE_NAME = 'games/focus_finder.html'

    DIFFICULTY_CONFIGS = {
        1: {'rows': 2, 'cols': 3, 'total_items': 6, 'same_cat_count': 0},
        2: {'rows': 3, 'cols': 3, 'total_items': 9, 'same_cat_count': 1},
        3: {'rows': 3, 'cols': 4, 'total_items': 12, 'same_cat_count': 2},
        4: {'rows': 4, 'cols': 4, 'total_items': 16, 'same_cat_count': 3},
        5: {'rows': 4, 'cols': 5, 'total_items': 20, 'same_cat_count': 4},
    }

    @classmethod
    def get_instructions(cls):
        """
        Elder-friendly step-by-step instructions for the Focus Finder intro screen.
        """
        return [
            {
                'number': 1,
                'title': "Look at the Target Item",
                'description': "You will see a reference card showing one everyday object or flower to find.",
            },
            {
                'number': 2,
                'title': "Scan the Picture Grid",
                'description': "Look across the calm grid at your own pace. There is no timer or hurry.",
            },
            {
                'number': 3,
                'title': "Tap Your Choice",
                'description': "Tap the tile that matches the target. You can change your selection at any time without penalty.",
            },
            {
                'number': 4,
                'title': "Confirm & Receive Gentle Feedback",
                'description': "Press \"Confirm My Selection\" to review your choice and complete 3 pleasant rounds.",
            },
        ]

    @classmethod
    def get_session_plan(cls, session=None, difficulty=1):
        """
        Deterministically plans 3 rounds for a session.
        Uses session ID and difficulty as seed so results are reproducible.
        Ensures 3 distinct target items across rounds.
        """
        if session and hasattr(session, 'difficulty'):
            diff = session.difficulty
        else:
            diff = difficulty

        diff_cfg = cls.DIFFICULTY_CONFIGS.get(diff, cls.DIFFICULTY_CONFIGS[1])
        total_items = diff_cfg['total_items']
        rows = diff_cfg['rows']
        cols = diff_cfg['cols']
        same_cat_target = diff_cfg['same_cat_count']

        s_id = session.id if (session and session.id) else 1
        base_seed = s_id * 1000 + diff * 10
        rng_session = random.Random(base_seed)

        all_keys = sorted(FOCUS_FINDER_CATALOG.keys())
        target_keys = rng_session.sample(all_keys, cls.TOTAL_ROUNDS)

        plan = {}
        for r in range(1, cls.TOTAL_ROUNDS + 1):
            target_key = target_keys[r - 1]
            target_item = FOCUS_FINDER_CATALOG[target_key]
            target_cat = target_item['category']

            same_cat = [k for k in all_keys if k != target_key and FOCUS_FINDER_CATALOG[k]['category'] == target_cat]
            diff_cat = [k for k in all_keys if k != target_key and FOCUS_FINDER_CATALOG[k]['category'] != target_cat]

            rng_round = random.Random(base_seed + r)

            needed = total_items - 1
            num_same = min(same_cat_target, len(same_cat), needed)
            chosen_same = rng_round.sample(same_cat, num_same) if num_same > 0 else []

            remaining_needed = needed - len(chosen_same)
            remaining_pool = diff_cat + [k for k in same_cat if k not in chosen_same]
            chosen_other = rng_round.sample(remaining_pool, remaining_needed)

            distractor_keys = chosen_same + chosen_other
            grid_keys = [target_key] + distractor_keys
            rng_round.shuffle(grid_keys)

            grid_items = [FOCUS_FINDER_CATALOG[k] for k in grid_keys]

            plan[r] = {
                'target_item': target_item,
                'target_ids': [target_key],
                'distractor_ids': distractor_keys,
                'grid_items': grid_items,
                'grid_item_ids': grid_keys,
                'grid_size': {'rows': rows, 'cols': cols},
            }
        return plan

    @classmethod
    def get_round_data(cls, round_number, session=None):
        if round_number not in (1, 2, 3):
            raise ValueError(f"Invalid round number {round_number}. Max rounds is {cls.TOTAL_ROUNDS}.")

        plan = cls.get_session_plan(session=session)
        round_plan = plan[round_number]

        return {
            'round_number': round_number,
            'total_rounds': cls.TOTAL_ROUNDS,
            'prompt_text': "Find the matching item in the grid below.",
            'target_item': round_plan['target_item'],
            'target_name': round_plan['target_item']['name'],
            'target_category': round_plan['target_item']['category'],
            'target_ids': round_plan['target_ids'],
            'grid_items': round_plan['grid_items'],
            'grid_item_ids': round_plan['grid_item_ids'],
            'grid_size': round_plan['grid_size'],
        }

    @classmethod
    def evaluate_round(cls, round_number, actual_selected_ids, response_time_ms, session=None):
        if round_number not in (1, 2, 3):
            raise ValueError(f"Invalid round number {round_number}.")

        round_data = cls.get_round_data(round_number, session=session)
        target_id = round_data['target_ids'][0]
        target_name = round_data['target_name']

        norm_selected = [str(x) for x in actual_selected_ids]
        is_correct = (len(norm_selected) == 1 and norm_selected[0] == target_id)

        if is_correct:
            correct_ids = [target_id]
            distractor_ids = []
            missed_ids = []
            mistake_count = 0
            score = 1
            feedback_message = f"Wonderful! You found the {target_name}."
            feedback_tone = "success"
        else:
            correct_ids = []
            distractor_ids = norm_selected
            missed_ids = [target_id]
            mistake_count = 1
            score = 0
            feedback_message = f"Good effort! The {target_name} was resting in the grid. Taking your time to search is what matters most."
            feedback_tone = "encouraging"

        return {
            'is_correct': is_correct,
            'score': score,
            'max_score': 1,
            'mistake_count': mistake_count,
            'correct_ids': correct_ids,
            'distractor_ids': distractor_ids,
            'missed_ids': missed_ids,
            'misplaced_ids': [],
            'target_name': target_name,
            'feedback_message': feedback_message,
            'feedback_tone': feedback_tone,
        }


# Global registry of game engines for modular expansion
GAME_ENGINES = {
    MemoryMarketEngine.SLUG: MemoryMarketEngine,
    DailyLifeJourneyEngine.SLUG: DailyLifeJourneyEngine,
    FamiliarFacesEngine.SLUG: FamiliarFacesEngine,
    FocusFinderEngine.SLUG: FocusFinderEngine,
}


def create_fresh_game_session(member, game_slug, difficulty=1):
    """
    Creates a new GameSession with status IN_PROGRESS.
    Each explicit Start Activity action creates a fresh session.
    """
    if member.role != Role.PATIENT:
        raise ValidationError("Only users with the PATIENT role can initiate a game session.")

    game = Game.objects.get(slug=game_slug, is_active=True)

    if game_slug == FamiliarFacesEngine.SLUG:
        people_count = member.familiar_people.filter(is_active=True).exclude(photo='').count()
        if people_count < FamiliarFacesEngine.MIN_PEOPLE_REQUIRED:
            raise ValidationError(
                f"Familiar Faces requires at least {FamiliarFacesEngine.MIN_PEOPLE_REQUIRED} active people with photos. Currently {people_count} are ready."
            )

    engine_cls = GAME_ENGINES.get(game_slug)
    if engine_cls and hasattr(engine_cls, 'ROUND_CONFIGS'):
        configured_max_score = sum(
            len(cfg['target_ids'])
            for cfg in engine_cls.ROUND_CONFIGS.values()
        )
    elif engine_cls and hasattr(engine_cls, 'TOTAL_MAX_SCORE'):
        configured_max_score = engine_cls.TOTAL_MAX_SCORE
    else:
        configured_max_score = 0

    session = GameSession.objects.create(
        member=member,
        game=game,
        difficulty=difficulty,
        status=GameSession.Status.IN_PROGRESS,
        score=0,
        max_score=configured_max_score,
        accuracy=Decimal('0.00'),
        total_time_ms=0,
    )
    return session


def record_round_submission(session, round_number, actual_selected_ids, response_time_ms, hints_used=0):
    """
    Validates and stores a GameRound record inside a GameSession.
    Ensures safe server-side calculation of expected response and correctness.
    """
    if session.status != GameSession.Status.IN_PROGRESS:
        raise ValidationError("Cannot submit rounds to a session that is already completed or abandoned.")

    engine_cls = GAME_ENGINES.get(session.game.slug)
    if not engine_cls:
        raise ValueError(f"No game engine found for game slug '{session.game.slug}'.")

    # Prevent duplicate round submissions
    if session.rounds.filter(round_number=round_number).exists():
        raise ValidationError(f"Round {round_number} has already been submitted for this session.")

    round_data = engine_cls.get_round_data(round_number, session=session)
    eval_result = engine_cls.evaluate_round(round_number, actual_selected_ids, response_time_ms, session=session)

    if session.game.slug == 'memory-market':
        stimulus_payload = {
            'target_items': round_data.get('target_items', []),
            'market_items': round_data.get('market_items', []),
        }
    elif session.game.slug == 'daily-life-journey':
        stimulus_payload = {
            'scenario_title': round_data.get('scenario_title', ''),
            'scenario_instruction': round_data.get('scenario_instruction', ''),
            'available_steps': round_data.get('available_steps', []),
        }
    elif session.game.slug == 'familiar-faces':
        stimulus_payload = {
            'target_id': round_data.get('target_ids', [''])[0],
            'choice_ids': [c['id'] for c in round_data.get('choices', [])],
        }
    elif session.game.slug == 'focus-finder':
        stimulus_payload = {
            'target_id': round_data.get('target_ids', [''])[0],
            'distractor_ids': [item['id'] for item in round_data.get('grid_items', []) if item['id'] != round_data.get('target_ids', [''])[0]],
            'grid_item_ids': [item['id'] for item in round_data.get('grid_items', [])],
            'grid_size': round_data.get('grid_size', {'rows': 2, 'cols': 3}),
        }
    else:
        stimulus_payload = round_data

    expected_payload = {
        'target_ids': round_data['target_ids'],
    }
    actual_payload = {
        'selected_ids': actual_selected_ids,
        'correct_ids': eval_result.get('correct_ids', []),
        'distractor_ids': eval_result.get('distractor_ids', []),
        'missed_ids': eval_result.get('missed_ids', []),
        'misplaced_ids': eval_result.get('misplaced_ids', []),
    }

    # Ensure non-negative integers for latency and mistakes
    safe_response_time = max(0, int(response_time_ms))
    safe_mistakes = max(0, int(eval_result['mistake_count']))
    safe_hints = max(0, int(hints_used))

    game_round = GameRound.objects.create(
        session=session,
        round_number=round_number,
        stimulus_data=stimulus_payload,
        expected_response=expected_payload,
        actual_response=actual_payload,
        is_correct=eval_result['is_correct'],
        response_time_ms=safe_response_time,
        mistake_count=safe_mistakes,
        hints_used=safe_hints,
    )

    has_next_round = round_number < engine_cls.TOTAL_ROUNDS

    return {
        'round_obj': game_round,
        'evaluation': eval_result,
        'has_next_round': has_next_round,
        'next_round_number': round_number + 1 if has_next_round else None,
        'total_rounds': engine_cls.TOTAL_ROUNDS,
    }


def finalize_game_session(session):
    """
    Finalizes an IN_PROGRESS session: computes final score, max_score, accuracy,
    and total_time_ms from child GameRound records, marking status COMPLETED.
    """
    if session.status == GameSession.Status.COMPLETED:
        return session

    rounds = list(session.rounds.all().order_by('round_number'))
    total_score = 0
    total_max_score = 0
    total_time = 0

    for r in rounds:
        actual = r.actual_response or {}
        correct_picks = actual.get('correct_ids', [])
        expected = r.expected_response or {}
        target_ids = expected.get('target_ids', [])

        total_score += len(correct_picks)
        total_max_score += len(target_ids)
        total_time += r.response_time_ms

    if total_max_score > 0:
        accuracy = Decimal(str(round((total_score / total_max_score) * 100, 2)))
    else:
        accuracy = Decimal('0.00')

    # Clamp accuracy between 0.00 and 100.00
    accuracy = max(Decimal('0.00'), min(Decimal('100.00'), accuracy))

    session.score = max(0, total_score)
    session.max_score = max(0, total_max_score)
    session.accuracy = accuracy
    session.total_time_ms = max(0, total_time)
    session.status = GameSession.Status.COMPLETED
    session.completed_at = timezone.now()
    session.save()

    return session
