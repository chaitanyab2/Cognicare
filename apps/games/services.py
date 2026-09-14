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



WORD_CONNECTIONS_CATALOG = {
    'baking_bread': {
        'scenario_id': 'baking_bread',
        'theme': 'Food & Kitchen',
        'prompt': 'Which item is essential for making traditional dough rise?',
        'concept': 'Baking Bread',
        'contextual_clue': 'Think of the natural ingredient that creates warm, airy loaves.',
        'target_word_id': 'yeast',
        'target_word': 'Yeast',
        'distractors': {
            1: [('teacup', 'Teacup'), ('hammer', 'Hammer'), ('umbrella', 'Umbrella')],
            2: [('frying_pan', 'Frying Pan'), ('refrigerator', 'Refrigerator'), ('blender', 'Blender')],
            3: [('honey', 'Honey'), ('vinegar', 'Vinegar'), ('olive_oil', 'Olive Oil'), ('cinnamon', 'Cinnamon')],
            4: [('cornstarch', 'Cornstarch'), ('gelatin', 'Gelatin'), ('cocoa', 'Cocoa Powder'), ('vanilla', 'Vanilla')],
            5: [('baking_tin', 'Baking Tin'), ('rolling_pin', 'Rolling Pin'), ('bread_knife', 'Bread Knife'), ('cooling_rack', 'Cooling Rack'), ('apron', 'Kitchen Apron')],
        },
        'explanation': 'Yeast is the living leavening agent that ferments and makes traditional bread dough rise.',
    },
    'sewing_basket': {
        'scenario_id': 'sewing_basket',
        'theme': 'Crafts & Trades',
        'prompt': 'Which tool is worn on the fingertip to push needles safely?',
        'concept': 'Sewing Basket',
        'contextual_clue': 'A small metal shield used when hand-stitching thick fabric.',
        'target_word_id': 'thimble',
        'target_word': 'Thimble',
        'distractors': {
            1: [('garden_rake', 'Garden Rake'), ('alarm_clock', 'Alarm Clock'), ('sailboat', 'Sailboat')],
            2: [('teaspoon', 'Teaspoon'), ('doorbell', 'Doorbell'), ('hairbrush', 'Hairbrush')],
            3: [('safety_pin', 'Safety Pin'), ('tape_measure', 'Tape Measure'), ('cushion', 'Pin Cushion'), ('button', 'Spare Button')],
            4: [('embroidery_hoop', 'Embroidery Hoop'), ('seam_ripper', 'Seam Ripper'), ('bobbin', 'Bobbin'), ('tailors_chalk', "Tailor's Chalk")],
            5: [('pinking_shears', 'Pinking Shears'), ('needle_threader', 'Needle Threader'), ('measuring_gauge', 'Sewing Gauge'), ('tracing_wheel', 'Tracing Wheel'), ('bodkin', 'Bodkin')],
        },
        'explanation': 'A thimble is worn over the fingertip to shield it while pushing a needle through tough cloth.',
    },
    'morning_gardening': {
        'scenario_id': 'morning_gardening',
        'theme': 'Garden & Nature',
        'prompt': 'Which vessel is traditionally used to sprinkle water gently on flowerbeds?',
        'concept': 'Tending the Garden',
        'contextual_clue': 'A handheld container with a spout and perforated rose.',
        'target_word_id': 'watering_can',
        'target_word': 'Watering Can',
        'distractors': {
            1: [('typewriter', 'Typewriter'), ('pillowcase', 'Pillowcase'), ('violin', 'Violin')],
            2: [('bookshelf', 'Bookshelf'), ('armchair', 'Armchair'), ('tea_kettle', 'Tea Kettle')],
            3: [('flower_pot', 'Flower Pot'), ('garden_trowel', 'Garden Trowel'), ('pruning_shears', 'Pruning Shears'), ('seed_packet', 'Seed Packet')],
            4: [('wheelbarrow', 'Wheelbarrow'), ('garden_kneeler', 'Garden Kneeler'), ('trellis', 'Plant Trellis'), ('compost_bin', 'Compost Bin')],
            5: [('sprinkler_head', 'Lawn Sprinkler'), ('hose_nozzle', 'Hose Nozzle'), ('rain_gauge', 'Rain Gauge'), ('soil_scoop', 'Soil Scoop'), ('plant_mister', 'Glass Mister')],
        },
        'explanation': 'A watering can is designed specifically to carry and sprinkle water gently onto delicate plants.',
    },
    'letter_writing': {
        'scenario_id': 'letter_writing',
        'theme': 'Daily Routines',
        'prompt': 'Which item is affixed to an envelope so postal carriers can deliver it?',
        'concept': 'Sending a Letter',
        'contextual_clue': 'A small gummed paper receipt showing postal payment.',
        'target_word_id': 'postage_stamp',
        'target_word': 'Postage Stamp',
        'distractors': {
            1: [('toaster', 'Toaster'), ('rain_boots', 'Rain Boots'), ('bicycle', 'Bicycle')],
            2: [('paper_clip', 'Paper Clip'), ('pencil_sharpener', 'Pencil Sharpener'), ('bookmark', 'Bookmark')],
            3: [('fountain_pen', 'Fountain Pen'), ('writing_pad', 'Writing Pad'), ('envelope', 'Postal Envelope'), ('sealing_wax', 'Sealing Wax')],
            4: [('rubber_stamp', 'Rubber Date Stamp'), ('blotting_paper', 'Blotting Paper'), ('letter_opener', 'Letter Opener'), ('address_book', 'Address Book')],
            5: [('postcard', 'Picture Postcard'), ('airmail_sticker', 'Airmail Label'), ('stationery_box', 'Stationery Box'), ('pen_holder', 'Wooden Pen Stand'), ('wax_seal_stamp', 'Embossing Seal')],
        },
        'explanation': 'A postage stamp is the official paper token affixed to an envelope confirming postal delivery fees.',
    },
    'afternoon_tea': {
        'scenario_id': 'afternoon_tea',
        'theme': 'Food & Kitchen',
        'prompt': 'Which utensil is used to hold loose tea leaves inside hot water while steeping?',
        'concept': 'Afternoon Tea',
        'contextual_clue': 'A small mesh sphere or perforated basket placed in the cup or pot.',
        'target_word_id': 'tea_infuser',
        'target_word': 'Tea Infuser',
        'distractors': {
            1: [('garden_rake', 'Garden Rake'), ('flashlight', 'Flashlight'), ('telescope', 'Telescope')],
            2: [('soup_ladle', 'Soup Ladle'), ('rolling_pin', 'Rolling Pin'), ('breadbox', 'Breadbox')],
            3: [('teacup', 'Teacup'), ('sugar_bowl', 'Sugar Bowl'), ('milk_pitcher', 'Milk Pitcher'), ('tea_cosy', 'Tea Cosy')],
            4: [('tea_tray', 'Serving Tray'), ('honey_dipper', 'Honey Dipper'), ('cake_stand', 'Cake Stand'), ('biscuit_tin', 'Biscuit Tin')],
            5: [('tea_strainer', 'Tea Strainer'), ('tea_caddy', 'Tea Caddy'), ('lemon_fork', 'Lemon Fork'), ('sugar_tongs', 'Sugar Tongs'), ('slop_bowl', 'Tea Slop Bowl')],
        },
        'explanation': 'A tea infuser holds dried tea leaves securely while allowing boiling water to circulate and steep.',
    },
    'rainy_weather': {
        'scenario_id': 'rainy_weather',
        'theme': 'Nature & Seasons',
        'prompt': 'Which protective item unfolds overhead to keep rain showers off?',
        'concept': 'Rainy Afternoon',
        'contextual_clue': 'A portable fabric canopy on ribs carried when dark clouds gather.',
        'target_word_id': 'umbrella',
        'target_word': 'Umbrella',
        'distractors': {
            1: [('harmonica', 'Harmonica'), ('desk_lamp', 'Desk Lamp'), ('flowerbed', 'Flowerbed')],
            2: [('beach_towel', 'Beach Towel'), ('sunhat', 'Straw Sunhat'), ('sunglasses', 'Sunglasses')],
            3: [('waterproof_boots', 'Rain Boots'), ('warm_scarf', 'Warm Scarf'), ('woolen_mittens', 'Woolen Mittens'), ('trenchcoat', 'Trenchcoat')],
            4: [('storm_lantern', 'Storm Lantern'), ('doormat', 'Mud Mat'), ('galoshes', 'Rubber Galoshes'), ('rain_gauge', 'Outdoor Rain Gauge')],
            5: [('umbrella_stand', 'Hall Umbrella Stand'), ('windbreaker', 'Windbreaker Jacket'), ('hatbox', 'Felt Hatbox'), ('walking_stick', 'Wooden Cane'), ('waterproof_hat', 'Souwester Hat')],
        },
        'explanation': 'An umbrella is designed specifically to open overhead and shield a person from falling rain.',
    },
    'carpentry_bench': {
        'scenario_id': 'carpentry_bench',
        'theme': 'Crafts & Trades',
        'prompt': 'Which hand tool is pushed along rough wood boards to shave them smooth and flat?',
        'concept': 'Woodworking Bench',
        'contextual_clue': 'A block tool with a sharp angled iron blade underneath.',
        'target_word_id': 'hand_plane',
        'target_word': 'Hand Plane',
        'distractors': {
            1: [('telephone', 'Telephone'), ('pillow', 'Bed Pillow'), ('cookbook', 'Cookbook')],
            2: [('garden_hose', 'Garden Hose'), ('frying_pan', 'Frying Pan'), ('washcloth', 'Washcloth')],
            3: [('claw_hammer', 'Claw Hammer'), ('handsaw', 'Handsaw'), ('tape_measure', 'Measuring Tape'), ('wood_glue', 'Wood Glue')],
            4: [('wood_chisel', 'Wood Chisel'), ('try_square', 'Carpenter Square'), ('bench_vise', 'Bench Vise'), ('sandpaper', 'Sandpaper Sheet')],
            5: [('marking_gauge', 'Marking Gauge'), ('spoke_shave', 'Spokeshave'), ('draw_knife', 'Drawknife'), ('coping_saw', 'Coping Saw'), ('wood_rasp', 'Cabinet Rasp')],
        },
        'explanation': 'A hand plane is pushed across timber surfaces to shave off thin curls and create a true, smooth plane.',
    },
    'autumn_fireplace': {
        'scenario_id': 'autumn_fireplace',
        'theme': 'Home & Hearth',
        'prompt': 'Which hearth tool is squeezed by hand to blow air and revive fading embers?',
        'concept': 'Living Room Fireplace',
        'contextual_clue': 'An accordion-like wooden tool with leather sides and a brass nozzle.',
        'target_word_id': 'fireplace_bellows',
        'target_word': 'Fireplace Bellows',
        'distractors': {
            1: [('wristwatch', 'Wristwatch'), ('watering_can', 'Watering Can'), ('paint_brush', 'Paint Brush')],
            2: [('dustpan', 'Dustpan'), ('window_curtain', 'Window Curtain'), ('carpet_sweeper', 'Carpet Sweeper')],
            3: [('iron_poker', 'Fire Poker'), ('log_grate', 'Hearth Grate'), ('kindling_bucket', 'Kindling Bucket'), ('spark_screen', 'Firescreen')],
            4: [('hearth_shovel', 'Ash Shovel'), ('fire_tongs', 'Log Tongs'), ('hearth_broom', 'Ash Broom'), ('log_basket', 'Firewood Basket')],
            5: [('andiron', 'Brass Andiron'), ('fender', 'Hearth Fender'), ('chimney_cap', 'Chimney Flue'), ('fire_starter', 'Flint Striker'), ('coal_scuttle', 'Coal Scuttle')],
        },
        'explanation': 'Fireplace bellows pump a concentrated blast of fresh air into the coals to kindle and feed the flames.',
    },
    'bedtime_routine': {
        'scenario_id': 'bedtime_routine',
        'theme': 'Daily Routines',
        'prompt': 'Which soft item filled with feathers or wool supports your head through the night?',
        'concept': 'Evening Bedtime',
        'contextual_clue': 'A comfortable resting cushion dressed in a clean cotton slip.',
        'target_word_id': 'bed_pillow',
        'target_word': 'Bed Pillow',
        'distractors': {
            1: [('watering_can', 'Watering Can'), ('lawnmower', 'Lawnmower'), ('bicycle_pump', 'Bicycle Pump')],
            2: [('dinner_plate', 'Dinner Plate'), ('soup_spoon', 'Soup Spoon'), ('kitchen_clock', 'Kitchen Clock')],
            3: [('bedside_lamp', 'Bedside Lamp'), ('warm_quilt', 'Warm Quilt'), ('alarm_clock', 'Alarm Clock'), ('slippers', 'House Slippers')],
            4: [('woolen_blanket', 'Woolen Blanket'), ('mattress_pad', 'Mattress Pad'), ('nightstand', 'Wooden Nightstand'), ('hot_water_bottle', 'Hot Water Bottle')],
            5: [('bolster_cushion', 'Bolster Cushion'), ('bedspread', 'Linen Bedspread'), ('feather_duvet', 'Feather Duvet'), ('sleep_mask', 'Silk Eye Mask'), ('valance_sheet', 'Bed Skirt')],
        },
        'explanation': 'A bed pillow provides head and neck support for restful sleep throughout the night.',
    },
    'baking_apple_pie': {
        'scenario_id': 'baking_apple_pie',
        'theme': 'Food & Kitchen',
        'prompt': 'Which aromatic sweet brown spice is traditionally sprinkled over baking apples?',
        'concept': 'Apple Pie Baking',
        'contextual_clue': 'A warm ground bark spice fragrant with comforting holiday aromas.',
        'target_word_id': 'cinnamon',
        'target_word': 'Ground Cinnamon',
        'distractors': {
            1: [('roller_skate', 'Roller Skate'), ('harmonica', 'Harmonica'), ('birdcage', 'Birdcage')],
            2: [('black_pepper', 'Black Pepper'), ('garlic_salt', 'Garlic Salt'), ('mustard_seed', 'Mustard Seed')],
            3: [('cane_sugar', 'Cane Sugar'), ('unsalted_butter', 'Unsalted Butter'), ('lemon_juice', 'Lemon Juice'), ('pastry_flour', 'Pastry Flour')],
            4: [('ground_nutmeg', 'Ground Nutmeg'), ('allspice', 'Ground Allspice'), ('ground_cloves', 'Ground Cloves'), ('vanilla_pod', 'Vanilla Pod')],
            5: [('pie_dish', 'Ceramic Pie Dish'), ('pastry_brush', 'Pastry Brush'), ('pie_crust_shield', 'Pie Crust Shield'), ('dough_blender', 'Pastry Blender'), ('apple_peeler', 'Apple Corer')],
        },
        'explanation': 'Cinnamon is the classic warm spice paired with apples in traditional homemade pies.',
    },
    'knitting_sweaters': {
        'scenario_id': 'knitting_sweaters',
        'theme': 'Crafts & Trades',
        'prompt': 'Which material wound into soft skeins or balls is knitted into warm garments?',
        'concept': 'Knitting a Warm Sweater',
        'contextual_clue': 'Spun strands of wool or cotton pulled loop by loop onto needles.',
        'target_word_id': 'knitting_yarn',
        'target_word': 'Spun Yarn',
        'distractors': {
            1: [('garden_rake', 'Garden Rake'), ('typewriter', 'Typewriter'), ('pocket_knife', 'Pocket Knife')],
            2: [('fishing_line', 'Fishing Line'), ('electrical_wire', 'Copper Wire'), ('twine', 'Garden Twine')],
            3: [('knitting_needles', 'Knitting Needles'), ('measuring_tape', 'Measuring Tape'), ('stitch_markers', 'Stitch Markers'), ('tapestry_needle', 'Tapestry Needle')],
            4: [('yarn_bowl', 'Ceramic Yarn Bowl'), ('row_counter', 'Row Counter'), ('stitch_holder', 'Stitch Holder'), ('crochet_hook', 'Crochet Hook')],
            5: [('skein_winder', 'Ball Winder'), ('yarn_swift', 'Wooden Yarn Swift'), ('blocking_mats', 'Blocking Board'), ('gauge_ruler', 'Needle Gauge'), ('yarn_gauge', 'Tension Square')],
        },
        'explanation': 'Spun yarn is the primary fibrous material knitted with needles to form blankets and sweaters.',
    },
    'morning_coffee': {
        'scenario_id': 'morning_coffee',
        'theme': 'Daily Routines',
        'prompt': 'Which countertop appliance uses burrs or blades to crush whole roasted coffee beans?',
        'concept': 'Fresh Morning Coffee',
        'contextual_clue': 'A mill used to turn whole aromatic beans into grounds before brewing.',
        'target_word_id': 'coffee_grinder',
        'target_word': 'Coffee Grinder',
        'distractors': {
            1: [('garden_spade', 'Garden Spade'), ('sewing_needle', 'Sewing Needle'), ('binoculars', 'Binoculars')],
            2: [('toaster', 'Bread Toaster'), ('waffle_iron', 'Waffle Iron'), ('can_opener', 'Can Opener')],
            3: [('coffee_mug', 'Ceramic Mug'), ('french_press', 'French Press'), ('coffee_pot', 'Glass Coffee Pot'), ('paper_filter', 'Paper Filter')],
            4: [('espresso_tamper', 'Espresso Tamper'), ('milk_frother', 'Milk Frother'), ('water_kettle', 'Pour-Over Kettle'), ('ceramic_dripper', 'Coffee Dripper')],
            5: [('beans_canister', 'Beans Canister'), ('coffee_scale', 'Digital Coffee Scale'), ('measuring_scoop', 'Coffee Scoop'), ('carafe_warmer', 'Carafe Warmer'), ('filter_stand', 'Filter Holder')],
        },
        'explanation': 'A coffee grinder crushes whole roasted beans into fresh grounds for brewing.',
    },
    'visiting_library': {
        'scenario_id': 'visiting_library',
        'theme': 'Community & Culture',
        'prompt': 'Which thin card or ribbon slips between pages to save your reading place?',
        'concept': 'A Quiet Afternoon at the Library',
        'contextual_clue': 'A gentle paper or ribbon keeper tucked inside a book.',
        'target_word_id': 'bookmark',
        'target_word': 'Bookmark',
        'distractors': {
            1: [('rolling_pin', 'Rolling Pin'), ('garden_hose', 'Garden Hose'), ('tea_kettle', 'Tea Kettle')],
            2: [('pencil_sharpener', 'Pencil Sharpener'), ('desk_ruler', 'Wooden Ruler'), ('paperweight', 'Glass Paperweight')],
            3: [('reading_glasses', 'Reading Glasses'), ('hardcover_book', 'Hardcover Book'), ('library_card', 'Library Card'), ('desk_lamp', 'Study Lamp')],
            4: [('bookends', 'Brass Bookends'), ('magnifying_glass', 'Magnifying Glass'), ('book_stand', 'Book Display Stand'), ('card_catalog', 'Card Catalog Drawer')],
            5: [('bookplate', 'Ex Libris Bookplate'), ('dust_jacket', 'Book Dust Jacket'), ('ribbon_marker', 'Bound Ribbon Page Marker'), ('book_pocket', 'Checkout Pocket'), ('stamp_pad', 'Due Date Stamp')],
        },
        'explanation': 'A bookmark is placed between the pages of a book to preserve your reading position safely.',
    },
    'autumn_orchard': {
        'scenario_id': 'autumn_orchard',
        'theme': 'Garden & Nature',
        'prompt': 'Which deep wooden container is traditionally used to collect harvested tree fruit?',
        'concept': 'Autumn Apple Orchard',
        'contextual_clue': 'A sturdy slatted box or woven vessel used during seasonal harvests.',
        'target_word_id': 'bushel_basket',
        'target_word': 'Bushel Basket',
        'distractors': {
            1: [('teacup', 'Teacup'), ('typewriter', 'Typewriter'), ('fireplace_poker', 'Fireplace Poker')],
            2: [('dustpan', 'Dustpan'), ('breadbox', 'Breadbox'), ('shoe_rack', 'Shoe Rack')],
            3: [('gardening_gloves', 'Gardening Gloves'), ('step_ladder', 'Step Ladder'), ('pruning_clippers', 'Pruning Clippers'), ('sun_hat', 'Canvas Sun Hat')],
            4: [('wooden_crate', 'Storage Crate'), ('cider_jug', 'Glass Cider Jug'), ('fruit_picker_pole', 'Fruit Picker Pole'), ('orchard_tarp', 'Harvest Tarp')],
            5: [('apple_press', 'Cider Press'), ('produce_scale', 'Hanging Produce Scale'), ('harvest_apron', 'Harvest Apron'), ('wheelbarrow', 'Garden Wheelbarrow'), ('fruit_sorter', 'Grading Sieve')],
        },
        'explanation': 'A bushel basket is the traditional woven container used to hold picked apples and pears in an orchard.',
    },
    'family_album': {
        'scenario_id': 'family_album',
        'theme': 'Community & Culture',
        'prompt': 'Which small decorative paper triangles hold vintage pictures securely onto album pages?',
        'concept': 'Family Photo Album',
        'contextual_clue': 'Adhesive corner tabs that hold photographs without damaging delicate backing.',
        'target_word_id': 'photo_corners',
        'target_word': 'Photo Corners',
        'distractors': {
            1: [('watering_can', 'Watering Can'), ('soup_ladle', 'Soup Ladle'), ('garden_rake', 'Garden Rake')],
            2: [('scotch_tape', 'Cellophane Tape'), ('paper_clip', 'Paper Clip'), ('rubber_band', 'Rubber Band')],
            3: [('picture_frame', 'Picture Frame'), ('album_page', 'Black Album Page'), ('fountain_pen', 'Fountain Pen'), ('magnifying_glass', 'Magnifying Glass')],
            4: [('tissue_interleaving', 'Glassine Tissue Sheet'), ('film_negative', 'Film Negative Sleeve'), ('keepsake_envelope', 'Keepsake Envelope'), ('scrapbook_binder', 'Leather Binder')],
            5: [('mounting_squares', 'Mounting Squares'), ('corner_punch', 'Corner Punch'), ('archival_glue', 'Acid-Free Glue Stick'), ('labeling_tabs', 'Embossed Labeling Tape'), ('slipcase', 'Album Slipcase')],
        },
        'explanation': 'Photo corners are adhesive pockets that gently hold the corners of photographs onto album pages without damaging them.',
    },
    'shoe_polishing': {
        'scenario_id': 'shoe_polishing',
        'theme': 'Daily Routines',
        'prompt': 'Which dense horsehair brush is used to buff polished leather to a lustrous shine?',
        'concept': 'Caring for Leather Shoes',
        'contextual_clue': 'A wooden-backed bristle brush rubbed vigorously across the shoe.',
        'target_word_id': 'buffing_brush',
        'target_word': 'Shoe Buffing Brush',
        'distractors': {
            1: [('harmonica', 'Harmonica'), ('tea_kettle', 'Tea Kettle'), ('garden_hose', 'Garden Hose')],
            2: [('hairbrush', 'Hairbrush'), ('toothbrush', 'Toothbrush'), ('paint_brush', 'Paint Brush')],
            3: [('shoe_polish_tin', 'Wax Polish Tin'), ('polishing_cloth', 'Cotton Buffing Rag'), ('shoe_horn', 'Brass Shoe Horn'), ('wooden_shoe_tree', 'Wooden Shoe Tree')],
            4: [('edge_dressing', 'Sole Edge Dressing'), ('saddle_soap', 'Saddle Soap'), ('welt_brush', 'Small Welt Brush'), ('dauber_brush', 'Polish Applicator Dauber')],
            5: [('chamois_leather', 'Chamois Leather'), ('shine_box', 'Wooden Valet Box'), ('leather_conditioner', 'Leather Balm'), ('waterproof_wax', 'Dubbin Wax'), ('heel_shifter', 'Heel Pad')],
        },
        'explanation': 'A shoe buffing brush made of horsehair creates friction to bring leather wax to a rich, warm shine.',
    },
    'flower_arranging': {
        'scenario_id': 'flower_arranging',
        'theme': 'Garden & Nature',
        'prompt': 'Which decorative glass or ceramic container holds water and displays fresh cut stems?',
        'concept': 'Arranging Fresh Flowers',
        'contextual_clue': 'A classic table vessel designed specifically to hold fresh-cut floral bouquets.',
        'target_word_id': 'flower_vase',
        'target_word': 'Flower Vase',
        'distractors': {
            1: [('bicycle_bell', 'Bicycle Bell'), ('alarm_clock', 'Alarm Clock'), ('typewriter', 'Typewriter')],
            2: [('soup_bowl', 'Soup Bowl'), ('coffee_mug', 'Coffee Mug'), ('water_jug', 'Water Pitcher')],
            3: [('floral_shears', 'Floral Shears'), ('garden_twine', 'Garden Twine'), ('plant_food_packet', 'Plant Food Packet'), ('ribbon', 'Satin Ribbon')],
            4: [('flower_frog', 'Metal Flower Frog'), ('floral_foam', 'Floral Foam Block'), ('stem_wire', 'Floral Stem Wire'), ('table_runner', 'Linen Table Runner')],
            5: [('urn_pedestal', 'Urn Pedestal'), ('rose_stripper', 'Thorn Stripper'), ('glass_marbles', 'Vase Filler Marbles'), ('floral_tape', 'Green Stem Tape'), ('water_pipette', 'Orchid Water Tube')],
        },
        'explanation': 'A flower vase is the dedicated vessel used to hold water and display freshly cut floral arrangements.',
    },
    'picnic_lunch': {
        'scenario_id': 'picnic_lunch',
        'theme': 'Community & Culture',
        'prompt': 'Which wide woven wicker container with handles and lids carries lunch into the park?',
        'concept': 'An Afternoon Picnic',
        'contextual_clue': 'A classic lidded hamper carried outdoors for alfresco meals.',
        'target_word_id': 'picnic_basket',
        'target_word': 'Picnic Basket',
        'distractors': {
            1: [('fireplace_poker', 'Fireplace Poker'), ('typewriter', 'Typewriter'), ('feather_pillow', 'Feather Pillow')],
            2: [('laundry_basket', 'Laundry Basket'), ('wastepaper_basket', 'Wastepaper Basket'), ('sewing_basket', 'Sewing Basket')],
            3: [('gingham_blanket', 'Checkered Blanket'), ('thermos_flask', 'Insulated Thermos'), ('cloth_napkins', 'Cloth Napkins'), ('sandwich_box', 'Sandwich Tin')],
            4: [('enamel_plates', 'Enamel Camp Plates'), ('cutlery_roll', 'Cutlery Roll'), ('salt_cellar', 'Travel Salt Shaker'), ('folding_corkscrew', 'Pocket Corkscrew')],
            5: [('picnic_rug_strap', 'Leather Blanket Carrier'), ('ice_flask', 'Cooler Flask'), ('bento_tins', 'Stacking Food Tins'), ('parasol', 'Paper Parasol'), ('canvas_cooler', 'Insulated Canvas Bag')],
        },
        'explanation': 'A picnic basket or wicker hamper is the traditional portable carrier for outdoor lunches and tablecloths.',
    },
    'winter_hearth': {
        'scenario_id': 'winter_hearth',
        'theme': 'Home & Hearth',
        'prompt': 'Which small, dry twigs and wood splinters catch sparks easily to ignite large logs?',
        'concept': 'Building a Winter Fire',
        'contextual_clue': 'Slender dry wood used between crumpled paper and heavy firewood.',
        'target_word_id': 'kindling',
        'target_word': 'Dry Kindling',
        'distractors': {
            1: [('rubber_duck', 'Rubber Duck'), ('alarm_clock', 'Alarm Clock'), ('bicycle_helmet', 'Bicycle Helmet')],
            2: [('dry_leaves', 'Raked Leaves'), ('sawdust', 'Sawdust'), ('newspaper', 'Old Newspaper')],
            3: [('oak_firewood', 'Heavy Oak Logs'), ('iron_poker', 'Fire Poker'), ('fireplace_hearth', 'Stone Hearth'), ('ash_bucket', 'Ash Bucket')],
            4: [('matches_box', 'Safety Matches'), ('fire_bellows', 'Hearth Bellows'), ('fatwood_sticks', 'Resinous Pine Sticks'), ('chimney_grate', 'Cast Iron Grate')],
            5: [('fire_tongs', 'Log Tongs'), ('hearth_fender', 'Brass Hearth Fender'), ('birch_bark', 'Dried Birch Bark Strips'), ('spark_screen', 'Mesh Fireplace Screen'), ('ember_rake', 'Ember Rake')],
        },
        'explanation': 'Kindling consists of dry, thin sticks that catch fire easily and produce enough sustained heat to ignite heavy logs.',
    },
    'morning_shave': {
        'scenario_id': 'morning_shave',
        'theme': 'Daily Routines',
        'prompt': 'Which soft bristle tool is swirled in a mug with soap to whip up rich lather?',
        'concept': 'Traditional Morning Shave',
        'contextual_clue': 'A wooden or resin handle with dense badger or boar hair bristles.',
        'target_word_id': 'shaving_brush',
        'target_word': 'Shaving Brush',
        'distractors': {
            1: [('garden_spade', 'Garden Spade'), ('rolling_pin', 'Rolling Pin'), ('harmonica', 'Harmonica')],
            2: [('hairbrush', 'Hairbrush'), ('toothbrush', 'Toothbrush'), ('shoe_brush', 'Shoe Brush')],
            3: [('safety_razor', 'Safety Razor'), ('shaving_soap', 'Shaving Soap Puck'), ('warm_towel', 'Warm Face Towel'), ('aftershave_lotion', 'Aftershave Splash')],
            4: [('shaving_mug', 'Ceramic Shave Mug'), ('leather_strop', 'Leather Strop'), ('alum_block', 'Alum Block'), ('razor_stand', 'Chrome Razor Stand')],
            5: [('styptic_pencil', 'Styptic Pencil'), ('shaving_scuttle', 'Hot Water Scuttle'), ('blade_dispenser', 'Razor Blade Pack'), ('pre_shave_oil', 'Pre-Shave Oil'), ('mirror_stand', 'Magnifying Shave Mirror')],
        },
        'explanation': 'A shaving brush whips warm water and soap into a thick, protective lather applied to the face.',
    },
    'pottery_wheel': {
        'scenario_id': 'pottery_wheel',
        'theme': 'Crafts & Trades',
        'prompt': 'Which natural pliable earth material is shaped by hand on a spinning wheel?',
        'concept': 'Working with Pottery',
        'contextual_clue': 'Moist mineral soil molded into bowls and baked in a kiln.',
        'target_word_id': 'pottery_clay',
        'target_word': 'Pottery Clay',
        'distractors': {
            1: [('alarm_clock', 'Alarm Clock'), ('typewriter', 'Typewriter'), ('frying_pan', 'Frying Pan')],
            2: [('garden_soil', 'Garden Soil'), ('sandpaper', 'Sandpaper'), ('flour_dough', 'Flour Dough')],
            3: [('potters_wheel', "Potter's Wheel"), ('water_sponge', 'Pottery Sponge'), ('ceramic_glaze', 'Ceramic Glaze'), ('pottery_kiln', 'Firing Kiln')],
            4: [('wire_cutter', 'Wire Clay Cutter'), ('wooden_rib', 'Shaping Rib'), ('carving_loop', 'Loop Carving Tool'), ('canvas_board', 'Wedging Board')],
            5: [('bat_pins', 'Wheel Bat Pins'), ('slip_cup', 'Clay Slip Cup'), ('calipers', 'Pottery Calipers'), ('sculpting_needle', 'Needle Tool'), ('banding_wheel', 'Banding Wheel')],
        },
        'explanation': 'Clay is the natural, malleable earthen material centered and shaped by hand on the potter’s wheel.',
    },
    'herb_garden': {
        'scenario_id': 'herb_garden',
        'theme': 'Garden & Nature',
        'prompt': 'Which fragrant needle-leafed evergreen herb is often paired with roasted potatoes?',
        'concept': 'Kitchen Herb Garden',
        'contextual_clue': 'A woody Mediterranean bush with pine-like aroma used in roasting.',
        'target_word_id': 'rosemary',
        'target_word': 'Fresh Rosemary',
        'distractors': {
            1: [('teacup', 'Teacup'), ('harmonica', 'Harmonica'), ('lawnmower', 'Lawnmower')],
            2: [('pine_needle', 'Pine Needle'), ('clover', 'Clover Leaf'), ('oak_leaf', 'Oak Leaf')],
            3: [('garden_trowel', 'Garden Trowel'), ('herb_shears', 'Herb Shears'), ('plant_marker', 'Slate Plant Marker'), ('terracotta_pot', 'Terracotta Pot')],
            4: [('fresh_parsley', 'Fresh Parsley'), ('sweet_basil', 'Sweet Basil'), ('garden_thyme', 'Garden Thyme'), ('garden_mint', 'Spearmint')],
            5: [('sage_leaves', 'Garden Sage'), ('french_tarragon', 'French Tarragon'), ('winter_savory', 'Winter Savory'), ('bay_laurel', 'Bay Laurel Leaves'), ('marjoram', 'Sweet Marjoram')],
        },
        'explanation': 'Rosemary is the aromatic, needle-leaved garden herb traditionally roasted with potatoes and meats.',
    },
    'sunday_baking': {
        'scenario_id': 'sunday_baking',
        'theme': 'Food & Kitchen',
        'prompt': 'Which heavy wooden or marble cylinder is rolled back and forth to flatten pastry dough?',
        'concept': 'Making Homemade Pies',
        'contextual_clue': 'A smooth cylindrical roller with handles on both ends.',
        'target_word_id': 'rolling_pin',
        'target_word': 'Rolling Pin',
        'distractors': {
            1: [('garden_rake', 'Garden Rake'), ('telephone', 'Telephone'), ('violin', 'Violin')],
            2: [('hammer', 'Hammer'), ('frying_pan', 'Frying Pan'), ('soup_spoon', 'Soup Spoon')],
            3: [('pastry_board', 'Pastry Board'), ('mixing_bowl', 'Mixing Bowl'), ('measuring_cup', 'Measuring Cup'), ('pastry_cutter', 'Pastry Cutter')],
            4: [('pie_tin', 'Pie Dish'), ('dough_scraper', 'Bench Scraper'), ('flour_sifter', 'Flour Sifter'), ('pastry_brush', 'Pastry Brush')],
            5: [('marble_board', 'Marble Pastry Slab'), ('pie_weights', 'Ceramic Pie Weights'), ('lattice_cutter', 'Pastry Lattice Roller'), ('crust_crimper', 'Pie Crust Fluter'), ('dough_docking_tool', 'Dough Docker')],
        },
        'explanation': 'A rolling pin is rolled across dough to flatten it to an even, uniform thickness for pies and tarts.',
    },
    'evening_reading': {
        'scenario_id': 'evening_reading',
        'theme': 'Home & Hearth',
        'prompt': 'Which optical instrument with framed convex glass rests on the nose to clarify small print?',
        'concept': 'Quiet Evening Reading',
        'contextual_clue': 'A pair of corrective lenses worn to bring book pages into sharp focus.',
        'target_word_id': 'reading_glasses',
        'target_word': 'Reading Glasses',
        'distractors': {
            1: [('garden_spade', 'Garden Spade'), ('teapot', 'Teapot'), ('rain_boots', 'Rain Boots')],
            2: [('sunglasses', 'Sunglasses'), ('pocket_watch', 'Pocket Watch'), ('compass', 'Pocket Compass')],
            3: [('bookmark', 'Silk Bookmark'), ('hardcover_book', 'Hardcover Book'), ('bedside_lamp', 'Bedside Lamp'), ('armchair', 'Reading Armchair')],
            4: [('magnifying_glass', 'Handheld Magnifier'), ('eyeglass_case', 'Hard Eyeglass Case'), ('cleaning_cloth', 'Microfiber Lens Cloth'), ('book_light', 'Clip-on Book Light')],
            5: [('bifocals', 'Bifocal Lenses'), ('pince_nez', 'Pince-Nez Spectacles'), ('opera_glasses', 'Opera Glasses'), ('spectacle_chain', 'Eyeglass Neck Cord'), ('reading_loupe', 'Jeweler Loupe')],
        },
        'explanation': 'Reading glasses magnify close-up printed text, making books and newspapers clear and easy to read.',
    },
}


class WordConnectionsEngine:
    """
    Game Engine for Word Connections (Semantic Memory & Association).
    Elder-friendly semantic recognition and contextual pairing activity
    with deterministic scenario generation and nuanced distractors across 5 difficulty levels.
    """
    SLUG = 'word-connections'
    TOTAL_ROUNDS = 3
    TOTAL_MAX_SCORE = 3
    TEMPLATE_NAME = 'games/word_connections.html'

    CHOICE_COUNTS = {
        1: 4,
        2: 4,
        3: 5,
        4: 5,
        5: 6,
    }

    @classmethod
    def get_instructions(cls):
        """
        Elder-friendly step-by-step instructions for the Word Connections intro screen.
        """
        return [
            {
                'number': 1,
                'title': "Read the Central Concept",
                'description': "You will see an everyday theme or activity on the main card, along with a helpful contextual clue.",
            },
            {
                'number': 2,
                'title': "Review the Word Options",
                'description': "Read through the word choices below at your own pace. There are no timers or rushing.",
            },
            {
                'number': 3,
                'title': "Select the Matching Word",
                'description': "Tap the card that has the closest natural connection. You can change your choice anytime without penalty.",
            },
            {
                'number': 4,
                'title': "Confirm & Receive Gentle Feedback",
                'description': "Press \"Confirm My Selection\" to review the connection and complete 3 pleasant rounds.",
            },
        ]

    @classmethod
    def get_session_plan(cls, session=None, difficulty=1):
        """
        Deterministically plans 3 rounds for a session.
        Uses session ID and difficulty as seed so results are reproducible.
        Ensures 3 distinct scenarios across rounds.
        """
        if session and hasattr(session, 'difficulty'):
            diff = session.difficulty
        else:
            diff = difficulty

        diff = max(1, min(5, diff))
        s_id = session.id if (session and session.id) else 1
        base_seed = s_id * 1000 + diff * 10
        rng_session = random.Random(base_seed)

        all_keys = sorted(WORD_CONNECTIONS_CATALOG.keys())
        chosen_keys = rng_session.sample(all_keys, cls.TOTAL_ROUNDS)

        plan = {}
        for r in range(1, cls.TOTAL_ROUNDS + 1):
            s_key = chosen_keys[r - 1]
            scenario = WORD_CONNECTIONS_CATALOG[s_key]
            target_id = scenario['target_word_id']
            target_word = scenario['target_word']
            distractors_list = scenario['distractors'].get(diff, scenario['distractors'][1])

            choices = [{'id': target_id, 'word': target_word}] + [
                {'id': d[0], 'word': d[1]} for d in distractors_list
            ]
            rng_round = random.Random(base_seed + r)
            rng_round.shuffle(choices)

            plan[r] = {
                'scenario_id': s_key,
                'theme': scenario['theme'],
                'prompt': scenario['prompt'],
                'concept': scenario['concept'],
                'contextual_clue': scenario['contextual_clue'],
                'target_word_id': target_id,
                'target_word': target_word,
                'target_ids': [target_id],
                'distractor_ids': [d[0] for d in distractors_list],
                'choices': choices,
                'choice_ids': [c['id'] for c in choices],
                'explanation': scenario['explanation'],
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
            'scenario_id': round_plan['scenario_id'],
            'theme': round_plan['theme'],
            'prompt': round_plan['prompt'],
            'concept': round_plan['concept'],
            'contextual_clue': round_plan['contextual_clue'],
            'target_word_id': round_plan['target_word_id'],
            'target_word': round_plan['target_word'],
            'target_ids': round_plan['target_ids'],
            'distractor_ids': round_plan['distractor_ids'],
            'choices': round_plan['choices'],
            'choice_ids': round_plan['choice_ids'],
            'explanation': round_plan['explanation'],
        }

    @classmethod
    def evaluate_round(cls, round_number, actual_selected_ids, response_time_ms, session=None):
        if round_number not in (1, 2, 3):
            raise ValueError(f"Invalid round number {round_number}.")

        round_data = cls.get_round_data(round_number, session=session)
        target_id = round_data['target_ids'][0]
        target_word = round_data['target_word']
        explanation = round_data['explanation']

        norm_selected = [str(x) for x in actual_selected_ids]
        is_correct = (len(norm_selected) == 1 and norm_selected[0] == target_id)

        if is_correct:
            correct_ids = [target_id]
            distractor_ids = []
            missed_ids = []
            mistake_count = 0
            score = 1
            feedback_message = f"Wonderful! {explanation}"
            feedback_tone = "success"
        else:
            correct_ids = []
            distractor_ids = norm_selected
            missed_ids = [target_id]
            mistake_count = 1
            score = 0
            feedback_message = f"Good effort! The closest connection is {target_word}. {explanation}"
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
            'target_word': target_word,
            'explanation': explanation,
            'feedback_message': feedback_message,
            'feedback_tone': feedback_tone,
        }




# ==========================================================================
# Phase 11: Pattern Detective (Visual Pattern Recognition) Catalog & Engine
# ==========================================================================

import xml.etree.ElementTree as ET
import sys
import os

# Base SVG templates (viewBox 0 0 64 64)
# Colors:
# Teal: #0F766E, #0D9488, #14B8A6, #CCFBF1, #F0FDFA
# Amber: #B45309, #D97706, #F59E0B, #FDE68A, #FEF3C7
# Indigo: #3730A3, #4338CA, #4F46E5, #C7D2FE, #EEF2FF
# Blue: #1D4ED8, #2563EB, #3B82F6, #DBEAFE, #EFF6FF
# Terracotta: #C2410C, #EA580C, #FB923C, #FFEDD5, #FFF7ED
# Rose: #BE185D, #DB2777, #EC4899, #FCE7F3, #FDF2F8

def make_circle(fill, stroke, stroke_w=2.5, r=22, cx=32, cy=32, extra=''):
    return f'''<svg viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg" role="img">
  <circle cx="{cx}" cy="{cy}" r="{r}" fill="{fill}" stroke="{stroke}" stroke-width="{stroke_w}"/>
  {extra}
</svg>'''

def make_square(fill, stroke, stroke_w=2.5, x=12, y=12, w=40, h=40, rx=4, extra=''):
    return f'''<svg viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg" role="img">
  <rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{fill}" stroke="{stroke}" stroke-width="{stroke_w}"/>
  {extra}
</svg>'''

def make_triangle(fill, stroke, stroke_w=2.5, extra=''):
    return f'''<svg viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg" role="img">
  <path d="M32 10L54 50H10L32 10Z" fill="{fill}" stroke="{stroke}" stroke-width="{stroke_w}" stroke-linejoin="round"/>
  {extra}
</svg>'''

def make_diamond(fill, stroke, stroke_w=2.5, extra=''):
    return f'''<svg viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg" role="img">
  <path d="M32 8L54 32L32 56L10 32L32 8Z" fill="{fill}" stroke="{stroke}" stroke-width="{stroke_w}"/>
  {extra}
</svg>'''

def make_sun(fill, stroke, ray_stroke):
    return f'''<svg viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg" role="img">
  <circle cx="32" cy="32" r="14" fill="{fill}" stroke="{stroke}" stroke-width="2.5"/>
  <path d="M32 6V14M32 50V58M6 32H14M50 32H58M14 14L20 20M44 44L50 50M14 50L20 44M44 20L50 14" stroke="{ray_stroke}" stroke-width="3" stroke-linecap="round"/>
</svg>'''

def make_leaf(fill, stroke):
    return f'''<svg viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg" role="img">
  <path d="M32 10C20 18 16 34 32 54C48 34 44 18 32 10Z" fill="{fill}" stroke="{stroke}" stroke-width="3"/>
  <path d="M32 20V46M32 30L24 24M32 38L40 32" stroke="{stroke}" stroke-width="2.5" stroke-linecap="round"/>
</svg>'''

def make_star(fill, stroke):
    return f'''<svg viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg" role="img">
  <path d="M32 8L38 24L55 24L41 35L46 51L32 41L18 51L23 35L9 24L26 24L32 8Z" fill="{fill}" stroke="{stroke}" stroke-width="2.5" stroke-linejoin="round"/>
</svg>'''

def make_cross(fill, stroke):
    return f'''<svg viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg" role="img">
  <path d="M24 10H40V24H54V40H40V54H24V40H10V24H24V10Z" fill="{fill}" stroke="{stroke}" stroke-width="2.5" stroke-linejoin="round"/>
</svg>'''

def make_lotus(fill, stroke, inner_fill, inner_stroke):
    return f'''<svg viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg" role="img">
  <path d="M32 14C36 24 44 32 48 44C38 46 34 40 32 36C30 40 26 46 16 44C20 32 28 24 32 14Z" fill="{fill}" stroke="{stroke}" stroke-width="2.5"/>
  <path d="M32 28C38 34 46 38 44 48C36 48 34 44 32 40C30 44 28 48 20 48C18 38 26 34 32 28Z" fill="{inner_fill}" stroke="{inner_stroke}" stroke-width="2"/>
</svg>'''

def make_diya(fill, stroke, flame_fill, flame_stroke):
    return f'''<svg viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg" role="img">
  <path d="M12 36C12 48 24 54 32 54C40 54 52 48 52 36H12Z" fill="{fill}" stroke="{stroke}" stroke-width="2.5"/>
  <path d="M32 14C35 22 40 26 36 34C34 36 30 36 28 34C24 26 29 22 32 14Z" fill="{flame_fill}" stroke="{flame_stroke}" stroke-width="2"/>
</svg>'''

def make_ring(stroke, stroke_w=5, r=22):
    return f'''<svg viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg" role="img">
  <circle cx="32" cy="32" r="{r}" stroke="{stroke}" stroke-width="{stroke_w}" fill="none"/>
</svg>'''

def make_dot(fill, stroke, r=16):
    return f'''<svg viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg" role="img">
  <circle cx="32" cy="32" r="{r}" fill="{fill}" stroke="{stroke}" stroke-width="2.5"/>
</svg>'''

def make_pointer(rotation_deg, stroke='#0F766E', fill='#CCFBF1'):
    # rotation around center 32, 32
    return f'''<svg viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg" role="img">
  <g transform="rotate({rotation_deg} 32 32)">
    <circle cx="32" cy="32" r="22" fill="{fill}" stroke="{stroke}" stroke-width="2"/>
    <path d="M32 14L40 28H34V46H30V28H24L32 14Z" fill="{stroke}" stroke="{stroke}" stroke-width="1.5" stroke-linejoin="round"/>
  </g>
</svg>'''

def make_crescent(rotation_deg, fill='#FEF3C7', stroke='#D97706'):
    return f'''<svg viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg" role="img">
  <g transform="rotate({rotation_deg} 32 32)">
    <path d="M32 12C43.0457 12 52 20.9543 52 32C52 43.0457 43.0457 52 32 52C28.2 52 24.6 50.9 21.6 49C29.6 46.5 35.4 39.5 35.4 32C35.4 24.5 29.6 17.5 21.6 15C24.6 13.1 28.2 12 32 12Z" fill="{fill}" stroke="{stroke}" stroke-width="2"/>
  </g>
</svg>'''

def make_feather(is_right, stroke='#0F766E', fill='#CCFBF1'):
    # left vs right reflection
    scale_x = '1' if is_right else '-1'
    return f'''<svg viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg" role="img">
  <g transform="translate(32 32) scale({scale_x} 1) translate(-32 -32)">
    <path d="M22 52C22 52 24 36 34 26C42 18 48 12 48 12C48 12 44 20 40 30C36 40 28 48 22 52Z" fill="{fill}" stroke="{stroke}" stroke-width="2.5"/>
    <path d="M22 52L48 12" stroke="{stroke}" stroke-width="2" stroke-linecap="round"/>
    <path d="M30 40L38 42M34 32L42 34M38 24L44 26" stroke="{stroke}" stroke-width="2" stroke-linecap="round"/>
  </g>
</svg>'''

def make_pinwheel_quadrant(active_quadrant):
    # active_quadrant: 'top', 'right', 'bottom', 'left', or 'all'
    c_off = '#E2E8F0'
    s_off = '#94A3B8'
    c_on = '#F59E0B'
    s_on = '#B45309'
    
    t_c, t_s = (c_on, s_on) if (active_quadrant in ('top', 'all')) else (c_off, s_off)
    r_c, r_s = (c_on, s_on) if (active_quadrant in ('right', 'all')) else (c_off, s_off)
    b_c, b_s = (c_on, s_on) if (active_quadrant in ('bottom', 'all')) else (c_off, s_off)
    l_c, l_s = (c_on, s_on) if (active_quadrant in ('left', 'all')) else (c_off, s_off)
    
    return f'''<svg viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg" role="img">
  <circle cx="32" cy="18" r="9" fill="{t_c}" stroke="{t_s}" stroke-width="2"/>
  <circle cx="46" cy="32" r="9" fill="{r_c}" stroke="{r_s}" stroke-width="2"/>
  <circle cx="32" cy="46" r="9" fill="{b_c}" stroke="{b_s}" stroke-width="2"/>
  <circle cx="18" cy="32" r="9" fill="{l_c}" stroke="{l_s}" stroke-width="2"/>
  <circle cx="32" cy="32" r="5" fill="#334155"/>
</svg>'''

def make_count_stars(count, fill='#FEF3C7', stroke='#D97706'):
    # Renders 1 to 5 stars neatly arranged
    coords = {
        1: [(32, 32)],
        2: [(20, 32), (44, 32)],
        3: [(16, 32), (32, 32), (48, 32)],
        4: [(20, 20), (44, 20), (20, 44), (44, 44)],
        5: [(20, 20), (44, 20), (32, 32), (20, 44), (44, 44)],
    }.get(count, [(32, 32)])
    
    paths = []
    r = 7 if count > 3 else (9 if count > 1 else 13)
    for cx, cy in coords:
        paths.append(f'''<polygon points="{cx},{cy-r} {cx+r*0.35},{cy-r*0.3} {cx+r},{cy-r*0.25} {cx+r*0.5},{cy+r*0.3} {cx+r*0.65},{cy+r} {cx},{cy+r*0.55} {cx-r*0.65},{cy+r} {cx-r*0.5},{cy+r*0.3} {cx-r},{cy-r*0.25} {cx-r*0.35},{cy-r*0.3}" fill="{fill}" stroke="{stroke}" stroke-width="1.5"/>''')
    
    return f'''<svg viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg" role="img">
  {' '.join(paths)}
</svg>'''

def make_striped_circle(stroke='#4338CA', fill='#EEF2FF'):
    return f'''<svg viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg" role="img">
  <circle cx="32" cy="32" r="22" fill="{fill}" stroke="{stroke}" stroke-width="3"/>
  <line x1="20" y1="18" x2="44" y2="46" stroke="{stroke}" stroke-width="2.5"/>
  <line x1="14" y1="32" x2="32" y2="50" stroke="{stroke}" stroke-width="2.5"/>
  <line x1="32" y1="14" x2="50" y2="32" stroke="{stroke}" stroke-width="2.5"/>
</svg>'''

def make_striped_triangle(stroke='#4338CA', fill='#EEF2FF'):
    return f'''<svg viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg" role="img">
  <path d="M32 10L54 50H10L32 10Z" fill="{fill}" stroke="{stroke}" stroke-width="3" stroke-linejoin="round"/>
  <line x1="24" y1="24" x2="40" y2="50" stroke="{stroke}" stroke-width="2.5"/>
  <line x1="16" y1="40" x2="28" y2="50" stroke="{stroke}" stroke-width="2.5"/>
  <line x1="32" y1="14" x2="50" y2="46" stroke="{stroke}" stroke-width="2.5"/>
</svg>'''

def make_shape_with_bar(shape_type, stroke='#0F766E', fill='#CCFBF1'):
    if shape_type == 'circle':
        return f'''<svg viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg" role="img">
  <circle cx="32" cy="32" r="20" fill="{fill}" stroke="{stroke}" stroke-width="2.5"/>
  <line x1="8" y1="32" x2="56" y2="32" stroke="{stroke}" stroke-width="4" stroke-linecap="round"/>
</svg>'''
    elif shape_type == 'triangle':
        return f'''<svg viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg" role="img">
  <path d="M32 12L52 50H12L32 12Z" fill="{fill}" stroke="{stroke}" stroke-width="2.5" stroke-linejoin="round"/>
  <line x1="8" y1="36" x2="56" y2="36" stroke="{stroke}" stroke-width="4" stroke-linecap="round"/>
</svg>'''
    elif shape_type == 'square':
        return f'''<svg viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg" role="img">
  <rect x="14" y="14" width="36" height="36" rx="4" fill="{fill}" stroke="{stroke}" stroke-width="2.5"/>
  <line x1="8" y1="32" x2="56" y2="32" stroke="{stroke}" stroke-width="4" stroke-linecap="round"/>
</svg>'''

PATTERN_DETECTIVE_CATALOG = {
    # -------------------------------------------------------------
    # LEVEL 1: Simple Alternating Sequences (3 choices)
    # -------------------------------------------------------------
    'lvl1_sun_leaf_alternate': {
        'puzzle_id': 'lvl1_sun_leaf_alternate',
        'difficulty': 1,
        'pattern_type': 'linear_alternating',
        'layout': 'linear_sequence',
        'title': 'Sun & Leaf Alternation',
        'prompt': 'Look at how the sun and leaf take turns. Which tile comes next?',
        'sequence': [
            {'tile_id': 'sun_gold', 'name': 'Golden Sun', 'svg': make_sun('#F59E0B', '#B45309', '#D97706')},
            {'tile_id': 'leaf_teal', 'name': 'Teal Leaf', 'svg': make_leaf('#CCFBF1', '#0F766E')},
            {'tile_id': 'sun_gold', 'name': 'Golden Sun', 'svg': make_sun('#F59E0B', '#B45309', '#D97706')},
            {'is_missing': True, 'position': 4},
        ],
        'target_tile': {
            'id': 'leaf_teal',
            'name': 'Teal Leaf',
            'svg': make_leaf('#CCFBF1', '#0F766E'),
        },
        'distractors': [
            {'id': 'sun_gold', 'name': 'Golden Sun', 'svg': make_sun('#F59E0B', '#B45309', '#D97706')},
            {'id': 'star_amber', 'name': 'Amber Star', 'svg': make_star('#FEF3C7', '#D97706')},
        ],
        'explanation': 'The pattern alternates between the Golden Sun and Teal Leaf. After the Sun, the next tile is the Teal Leaf.',
    },

    'lvl1_circle_square_alternate': {
        'puzzle_id': 'lvl1_circle_square_alternate',
        'difficulty': 1,
        'pattern_type': 'linear_alternating',
        'layout': 'linear_sequence',
        'title': 'Circle & Square Rhythm',
        'prompt': 'Which shape continues this alternating rhythm?',
        'sequence': [
            {'tile_id': 'circle_blue', 'name': 'Blue Circle', 'svg': make_circle('#DBEAFE', '#1D4ED8')},
            {'tile_id': 'square_terracotta', 'name': 'Terracotta Square', 'svg': make_square('#FFEDD5', '#C2410C')},
            {'tile_id': 'circle_blue', 'name': 'Blue Circle', 'svg': make_circle('#DBEAFE', '#1D4ED8')},
            {'is_missing': True, 'position': 4},
        ],
        'target_tile': {
            'id': 'square_terracotta',
            'name': 'Terracotta Square',
            'svg': make_square('#FFEDD5', '#C2410C'),
        },
        'distractors': [
            {'id': 'circle_blue', 'name': 'Blue Circle', 'svg': make_circle('#DBEAFE', '#1D4ED8')},
            {'id': 'diamond_teal', 'name': 'Teal Diamond', 'svg': make_diamond('#E0F2FE', '#0284C7')},
        ],
        'explanation': 'The pattern alternates between a Blue Circle and a Terracotta Square. The missing shape is the Terracotta Square.',
    },

    'lvl1_lotus_diya_alternate': {
        'puzzle_id': 'lvl1_lotus_diya_alternate',
        'difficulty': 1,
        'pattern_type': 'linear_alternating',
        'layout': 'linear_sequence',
        'title': 'Lotus & Diya Lamp',
        'prompt': 'The gentle garden alternates between a lotus flower and a diya lamp. Which one comes next?',
        'sequence': [
            {'tile_id': 'lotus_pink', 'name': 'Pink Lotus', 'svg': make_lotus('#FCE7F3', '#BE185D', '#F472B6', '#9D174D')},
            {'tile_id': 'diya_gold', 'name': 'Golden Diya', 'svg': make_diya('#FEF3C7', '#B45309', '#F59E0B', '#B45309')},
            {'tile_id': 'lotus_pink', 'name': 'Pink Lotus', 'svg': make_lotus('#FCE7F3', '#BE185D', '#F472B6', '#9D174D')},
            {'is_missing': True, 'position': 4},
        ],
        'target_tile': {
            'id': 'diya_gold',
            'name': 'Golden Diya',
            'svg': make_diya('#FEF3C7', '#B45309', '#F59E0B', '#B45309'),
        },
        'distractors': [
            {'id': 'lotus_pink', 'name': 'Pink Lotus', 'svg': make_lotus('#FCE7F3', '#BE185D', '#F472B6', '#9D174D')},
            {'id': 'leaf_teal', 'name': 'Teal Leaf', 'svg': make_leaf('#CCFBF1', '#0F766E')},
        ],
        'explanation': 'The sequence alternates between the Pink Lotus and the Golden Diya. The missing tile is the Golden Diya.',
    },

    'lvl1_diamond_cross_alternate': {
        'puzzle_id': 'lvl1_diamond_cross_alternate',
        'difficulty': 1,
        'pattern_type': 'linear_alternating',
        'layout': 'linear_sequence',
        'title': 'Diamond & Cross Border',
        'prompt': 'Which motif completes this balanced alternating border?',
        'sequence': [
            {'tile_id': 'diamond_teal', 'name': 'Teal Diamond', 'svg': make_diamond('#CCFBF1', '#0F766E')},
            {'tile_id': 'cross_amber', 'name': 'Amber Cross', 'svg': make_cross('#FEF3C7', '#D97706')},
            {'tile_id': 'diamond_teal', 'name': 'Teal Diamond', 'svg': make_diamond('#CCFBF1', '#0F766E')},
            {'is_missing': True, 'position': 4},
        ],
        'target_tile': {
            'id': 'cross_amber',
            'name': 'Amber Cross',
            'svg': make_cross('#FEF3C7', '#D97706'),
        },
        'distractors': [
            {'id': 'diamond_teal', 'name': 'Teal Diamond', 'svg': make_diamond('#CCFBF1', '#0F766E')},
            {'id': 'circle_amber', 'name': 'Amber Circle', 'svg': make_circle('#FEF3C7', '#D97706')},
        ],
        'explanation': 'The border alternates between the Teal Diamond and the Amber Cross. The missing tile is the Amber Cross.',
    },

    'lvl1_ring_dot_alternate': {
        'puzzle_id': 'lvl1_ring_dot_alternate',
        'difficulty': 1,
        'pattern_type': 'linear_alternating',
        'layout': 'linear_sequence',
        'title': 'Ring & Dot Harmony',
        'prompt': 'Notice how the hollow ring and solid dot alternate. What belongs in the empty space?',
        'sequence': [
            {'tile_id': 'ring_indigo', 'name': 'Indigo Ring', 'svg': make_ring('#3730A3')},
            {'tile_id': 'dot_amber', 'name': 'Amber Dot', 'svg': make_dot('#F59E0B', '#B45309')},
            {'tile_id': 'ring_indigo', 'name': 'Indigo Ring', 'svg': make_ring('#3730A3')},
            {'is_missing': True, 'position': 4},
        ],
        'target_tile': {
            'id': 'dot_amber',
            'name': 'Amber Dot',
            'svg': make_dot('#F59E0B', '#B45309'),
        },
        'distractors': [
            {'id': 'ring_indigo', 'name': 'Indigo Ring', 'svg': make_ring('#3730A3')},
            {'id': 'dot_indigo', 'name': 'Indigo Dot', 'svg': make_dot('#3730A3', '#1E1B4B')},
        ],
        'explanation': 'The pattern alternates between the Indigo Ring and the Amber Dot. Following the ring comes the Amber Dot.',
    },

    # -------------------------------------------------------------
    # LEVEL 2: 3-Item Cycles & Progressive Sequences (4 choices)
    # -------------------------------------------------------------
    'lvl2_three_color_cycle': {
        'puzzle_id': 'lvl2_three_color_cycle',
        'difficulty': 2,
        'pattern_type': 'linear_cycle',
        'layout': 'linear_sequence',
        'title': 'Tri-Color Blossom Cycle',
        'prompt': 'Three colors repeat in order: Gold, Teal, and Rose. Which blossom completes the second group?',
        'sequence': [
            {'tile_id': 'circle_gold', 'name': 'Golden Circle', 'svg': make_circle('#FEF3C7', '#D97706')},
            {'tile_id': 'circle_teal', 'name': 'Teal Circle', 'svg': make_circle('#CCFBF1', '#0F766E')},
            {'tile_id': 'circle_rose', 'name': 'Rose Circle', 'svg': make_circle('#FCE7F3', '#BE185D')},
            {'tile_id': 'circle_gold', 'name': 'Golden Circle', 'svg': make_circle('#FEF3C7', '#D97706')},
            {'tile_id': 'circle_teal', 'name': 'Teal Circle', 'svg': make_circle('#CCFBF1', '#0F766E')},
            {'is_missing': True, 'position': 6},
        ],
        'target_tile': {
            'id': 'circle_rose',
            'name': 'Rose Circle',
            'svg': make_circle('#FCE7F3', '#BE185D'),
        },
        'distractors': [
            {'id': 'circle_gold', 'name': 'Golden Circle', 'svg': make_circle('#FEF3C7', '#D97706')},
            {'id': 'circle_teal', 'name': 'Teal Circle', 'svg': make_circle('#CCFBF1', '#0F766E')},
            {'id': 'circle_indigo', 'name': 'Indigo Circle', 'svg': make_circle('#EEF2FF', '#4338CA')},
        ],
        'explanation': 'The cycle repeats Gold, Teal, then Rose. Following the second Teal circle comes the Rose Circle.',
    },

    'lvl2_size_growth_circles': {
        'puzzle_id': 'lvl2_size_growth_circles',
        'difficulty': 2,
        'pattern_type': 'size_progression',
        'layout': 'linear_sequence',
        'title': 'Expanding Teal Rings',
        'prompt': 'The teal rings expand in size with each step. Which ring continues the expansion?',
        'sequence': [
            {'tile_id': 'ring_teal_sm', 'name': 'Small Teal Ring', 'svg': make_ring('#0F766E', 4, 12)},
            {'tile_id': 'ring_teal_md', 'name': 'Medium Teal Ring', 'svg': make_ring('#0F766E', 4, 18)},
            {'tile_id': 'ring_teal_lg', 'name': 'Large Teal Ring', 'svg': make_ring('#0F766E', 4, 24)},
            {'is_missing': True, 'position': 4},
        ],
        'target_tile': {
            'id': 'ring_teal_xl',
            'name': 'Extra Large Teal Ring',
            'svg': make_ring('#0F766E', 4, 29),
        },
        'distractors': [
            {'id': 'ring_teal_sm', 'name': 'Small Teal Ring', 'svg': make_ring('#0F766E', 4, 12)},
            {'id': 'ring_teal_md', 'name': 'Medium Teal Ring', 'svg': make_ring('#0F766E', 4, 18)},
            {'id': 'square_teal_lg', 'name': 'Large Teal Square', 'svg': make_square('#CCFBF1', '#0F766E')},
        ],
        'explanation': 'Each ring grows progressively wider in diameter. The next size in the expansion is the Extra Large Teal Ring.',
    },

    'lvl2_shape_cycle_tri_sq_cir': {
        'puzzle_id': 'lvl2_shape_cycle_tri_sq_cir',
        'difficulty': 2,
        'pattern_type': 'linear_cycle',
        'layout': 'linear_sequence',
        'title': 'Geometric Trio Cycle',
        'prompt': 'The shapes repeat in order: Triangle, Square, Circle. Which shape follows the Triangle?',
        'sequence': [
            {'tile_id': 'tri_amber', 'name': 'Amber Triangle', 'svg': make_triangle('#FEF3C7', '#D97706')},
            {'tile_id': 'sq_teal', 'name': 'Teal Square', 'svg': make_square('#CCFBF1', '#0F766E')},
            {'tile_id': 'cir_indigo', 'name': 'Indigo Circle', 'svg': make_circle('#EEF2FF', '#3730A3')},
            {'tile_id': 'tri_amber', 'name': 'Amber Triangle', 'svg': make_triangle('#FEF3C7', '#D97706')},
            {'is_missing': True, 'position': 5},
        ],
        'target_tile': {
            'id': 'sq_teal',
            'name': 'Teal Square',
            'svg': make_square('#CCFBF1', '#0F766E'),
        },
        'distractors': [
            {'id': 'cir_indigo', 'name': 'Indigo Circle', 'svg': make_circle('#EEF2FF', '#3730A3')},
            {'id': 'tri_amber', 'name': 'Amber Triangle', 'svg': make_triangle('#FEF3C7', '#D97706')},
            {'id': 'star_amber', 'name': 'Amber Star', 'svg': make_star('#FEF3C7', '#D97706')},
        ],
        'explanation': 'The pattern sequence is Triangle, Square, Circle. After the second Triangle appears, the Square follows next.',
    },

    'lvl2_count_progression_dots': {
        'puzzle_id': 'lvl2_count_progression_dots',
        'difficulty': 2,
        'pattern_type': 'count_progression',
        'layout': 'linear_sequence',
        'title': 'Counting Golden Stars',
        'prompt': 'Each tile gains one golden star. Which tile continues the counting series?',
        'sequence': [
            {'tile_id': 'stars_1', 'name': '1 Golden Star', 'svg': make_count_stars(1)},
            {'tile_id': 'stars_2', 'name': '2 Golden Stars', 'svg': make_count_stars(2)},
            {'tile_id': 'stars_3', 'name': '3 Golden Stars', 'svg': make_count_stars(3)},
            {'is_missing': True, 'position': 4},
        ],
        'target_tile': {
            'id': 'stars_4',
            'name': '4 Golden Stars',
            'svg': make_count_stars(4),
        },
        'distractors': [
            {'id': 'stars_1', 'name': '1 Golden Star', 'svg': make_count_stars(1)},
            {'id': 'stars_3', 'name': '3 Golden Stars', 'svg': make_count_stars(3)},
            {'id': 'stars_5', 'name': '5 Golden Stars', 'svg': make_count_stars(5)},
        ],
        'explanation': 'The number of stars increases by one on each step (1, 2, 3). The missing tile contains 4 Golden Stars.',
    },

    'lvl2_celestial_trio_cycle': {
        'puzzle_id': 'lvl2_celestial_trio_cycle',
        'difficulty': 2,
        'pattern_type': 'linear_cycle',
        'layout': 'linear_sequence',
        'title': 'Celestial Trio Cycle',
        'prompt': 'The sky symbols repeat in a trio: Sun, Star, Moon. What symbol follows the Sun?',
        'sequence': [
            {'tile_id': 'sun_gold', 'name': 'Golden Sun', 'svg': make_sun('#F59E0B', '#B45309', '#D97706')},
            {'tile_id': 'star_amber', 'name': 'Amber Star', 'svg': make_star('#FEF3C7', '#D97706')},
            {'tile_id': 'crescent_teal', 'name': 'Teal Moon', 'svg': make_crescent(0, '#CCFBF1', '#0F766E')},
            {'tile_id': 'sun_gold', 'name': 'Golden Sun', 'svg': make_sun('#F59E0B', '#B45309', '#D97706')},
            {'is_missing': True, 'position': 5},
        ],
        'target_tile': {
            'id': 'star_amber',
            'name': 'Amber Star',
            'svg': make_star('#FEF3C7', '#D97706'),
        },
        'distractors': [
            {'id': 'crescent_teal', 'name': 'Teal Moon', 'svg': make_crescent(0, '#CCFBF1', '#0F766E')},
            {'id': 'sun_gold', 'name': 'Golden Sun', 'svg': make_sun('#F59E0B', '#B45309', '#D97706')},
            {'id': 'diamond_teal', 'name': 'Teal Diamond', 'svg': make_diamond('#CCFBF1', '#0F766E')},
        ],
        'explanation': 'The recurring group is Sun, Star, Moon. After the Sun returns, the Amber Star belongs in the next position.',
    },

    # -------------------------------------------------------------
    # LEVEL 3: 2D Relationships & Analogy Matrices (4 choices)
    # -------------------------------------------------------------
    'lvl3_matrix_shape_color': {
        'puzzle_id': 'lvl3_matrix_shape_color',
        'difficulty': 3,
        'pattern_type': 'matrix_analogy',
        'layout': 'matrix_2x2',
        'title': 'Shape & Color Harmony Grid',
        'prompt': 'Examine the rows and columns. Which shape and color combination completes the grid?',
        'matrix': [
            [
                {'tile_id': 'cir_teal', 'name': 'Teal Circle', 'svg': make_circle('#CCFBF1', '#0F766E')},
                {'tile_id': 'cir_amber', 'name': 'Amber Circle', 'svg': make_circle('#FEF3C7', '#D97706')},
            ],
            [
                {'tile_id': 'sq_teal', 'name': 'Teal Square', 'svg': make_square('#CCFBF1', '#0F766E')},
                {'is_missing': True, 'position': 4},
            ],
        ],
        'target_tile': {
            'id': 'sq_amber',
            'name': 'Amber Square',
            'svg': make_square('#FEF3C7', '#D97706'),
        },
        'distractors': [
            {'id': 'cir_amber', 'name': 'Amber Circle', 'svg': make_circle('#FEF3C7', '#D97706')},
            {'id': 'sq_teal', 'name': 'Teal Square', 'svg': make_square('#CCFBF1', '#0F766E')},
            {'id': 'sq_indigo', 'name': 'Indigo Square', 'svg': make_square('#EEF2FF', '#4338CA')},
        ],
        'explanation': 'Row 1 has Circles and Row 2 has Squares. Column 1 is Teal and Column 2 is Amber. The matching tile is the Amber Square.',
    },

    'lvl3_analogy_solid_to_outline': {
        'puzzle_id': 'lvl3_analogy_solid_to_outline',
        'difficulty': 3,
        'pattern_type': 'matrix_analogy',
        'layout': 'matrix_2x2',
        'title': 'Solid to Outline Analogy',
        'prompt': 'The top row changes from a solid shape to an outline. What happens to the rose blossom?',
        'matrix': [
            [
                {'tile_id': 'dia_solid', 'name': 'Solid Diamond', 'svg': make_diamond('#0F766E', '#0F766E')},
                {'tile_id': 'dia_outline', 'name': 'Outline Diamond', 'svg': make_diamond('none', '#0F766E', 4)},
            ],
            [
                {'tile_id': 'cir_solid', 'name': 'Solid Circle', 'svg': make_circle('#BE185D', '#BE185D')},
                {'is_missing': True, 'position': 4},
            ],
        ],
        'target_tile': {
            'id': 'cir_outline',
            'name': 'Outline Circle',
            'svg': make_circle('none', '#BE185D', 4),
        },
        'distractors': [
            {'id': 'cir_solid', 'name': 'Solid Circle', 'svg': make_circle('#BE185D', '#BE185D')},
            {'id': 'dia_outline', 'name': 'Outline Diamond', 'svg': make_diamond('none', '#0F766E', 4)},
            {'id': 'sq_outline', 'name': 'Outline Square', 'svg': make_square('none', '#BE185D', 4)},
        ],
        'explanation': 'Across each row, a solid filled shape becomes a hollow outline. The solid circle transforms into an Outline Circle.',
    },

    'lvl3_matrix_motif_fill': {
        'puzzle_id': 'lvl3_matrix_motif_fill',
        'difficulty': 3,
        'pattern_type': 'matrix_analogy',
        'layout': 'matrix_2x2',
        'title': 'Motif & Color Correspondence',
        'prompt': 'Look at the motifs in each row and the colors in each column. Which tile fits the empty corner?',
        'matrix': [
            [
                {'tile_id': 'leaf_teal', 'name': 'Teal Leaf', 'svg': make_leaf('#CCFBF1', '#0F766E')},
                {'tile_id': 'leaf_amber', 'name': 'Amber Leaf', 'svg': make_leaf('#FEF3C7', '#D97706')},
            ],
            [
                {'tile_id': 'sun_teal', 'name': 'Teal Sun', 'svg': make_sun('#CCFBF1', '#0F766E', '#0F766E')},
                {'is_missing': True, 'position': 4},
            ],
        ],
        'target_tile': {
            'id': 'sun_amber',
            'name': 'Amber Sun',
            'svg': make_sun('#FEF3C7', '#D97706', '#D97706'),
        },
        'distractors': [
            {'id': 'sun_teal', 'name': 'Teal Sun', 'svg': make_sun('#CCFBF1', '#0F766E', '#0F766E')},
            {'id': 'leaf_amber', 'name': 'Amber Leaf', 'svg': make_leaf('#FEF3C7', '#D97706')},
            {'id': 'sun_rose', 'name': 'Rose Sun', 'svg': make_sun('#FCE7F3', '#BE185D', '#BE185D')},
        ],
        'explanation': 'Row 1 displays leaves and Row 2 displays suns. Column 1 is teal and Column 2 is amber. The missing tile is the Amber Sun.',
    },

    'lvl3_striped_pattern_matrix': {
        'puzzle_id': 'lvl3_striped_pattern_matrix',
        'difficulty': 3,
        'pattern_type': 'matrix_analogy',
        'layout': 'matrix_2x2',
        'title': 'Texture Transformation Grid',
        'prompt': 'Notice how the first shape gains diagonal stripes in the second column. What belongs in the lower right?',
        'matrix': [
            [
                {'tile_id': 'cir_plain', 'name': 'Plain Indigo Circle', 'svg': make_circle('#EEF2FF', '#4338CA')},
                {'tile_id': 'cir_striped', 'name': 'Striped Indigo Circle', 'svg': make_striped_circle('#4338CA', '#EEF2FF')},
            ],
            [
                {'tile_id': 'tri_plain', 'name': 'Plain Indigo Triangle', 'svg': make_triangle('#EEF2FF', '#4338CA')},
                {'is_missing': True, 'position': 4},
            ],
        ],
        'target_tile': {
            'id': 'tri_striped',
            'name': 'Striped Indigo Triangle',
            'svg': make_striped_triangle('#4338CA', '#EEF2FF'),
        },
        'distractors': [
            {'id': 'tri_plain', 'name': 'Plain Indigo Triangle', 'svg': make_triangle('#EEF2FF', '#4338CA')},
            {'id': 'cir_striped', 'name': 'Striped Indigo Circle', 'svg': make_striped_circle('#4338CA', '#EEF2FF')},
            {'id': 'sq_striped', 'name': 'Striped Indigo Square', 'svg': make_square('#EEF2FF', '#4338CA')},
        ],
        'explanation': 'Moving horizontally adds diagonal stripes across the shape. The plain indigo triangle becomes the Striped Indigo Triangle.',
    },

    'lvl3_inner_core_matrix': {
        'puzzle_id': 'lvl3_inner_core_matrix',
        'difficulty': 3,
        'pattern_type': 'matrix_analogy',
        'layout': 'matrix_2x2',
        'title': 'Central Core Relationship',
        'prompt': 'A central dot is placed inside the shape in the second column. What happens to the terracotta square?',
        'matrix': [
            [
                {'tile_id': 'cir_empty', 'name': 'Hollow Teal Circle', 'svg': make_ring('#0F766E', 4)},
                {'tile_id': 'cir_with_dot', 'name': 'Teal Circle with Dot', 'svg': make_circle('#CCFBF1', '#0F766E', 2.5, 22, 32, 32, '<circle cx="32" cy="32" r="6" fill="#0F766E"/>')},
            ],
            [
                {'tile_id': 'sq_empty', 'name': 'Hollow Terracotta Square', 'svg': make_square('none', '#C2410C', 4)},
                {'is_missing': True, 'position': 4},
            ],
        ],
        'target_tile': {
            'id': 'sq_with_dot',
            'name': 'Terracotta Square with Dot',
            'svg': make_square('#FFEDD5', '#C2410C', 2.5, 12, 12, 40, 40, 4, '<circle cx="32" cy="32" r="6" fill="#C2410C"/>'),
        },
        'distractors': [
            {'id': 'sq_empty', 'name': 'Hollow Terracotta Square', 'svg': make_square('none', '#C2410C', 4)},
            {'id': 'cir_with_dot', 'name': 'Teal Circle with Dot', 'svg': make_circle('#CCFBF1', '#0F766E', 2.5, 22, 32, 32, '<circle cx="32" cy="32" r="6" fill="#0F766E"/>')},
            {'id': 'tri_with_dot', 'name': 'Triangle with Dot', 'svg': make_triangle('#FFEDD5', '#C2410C', 2.5, '<circle cx="32" cy="36" r="6" fill="#C2410C"/>')},
        ],
        'explanation': 'The pattern adds a central solid dot inside the outer border. The square gains a central dot, becoming Terracotta Square with Dot.',
    },

    # -------------------------------------------------------------
    # LEVEL 4: Rotation, Symmetry & Direction (5 choices)
    # -------------------------------------------------------------
    'lvl4_arrow_rotation_cw': {
        'puzzle_id': 'lvl4_arrow_rotation_cw',
        'difficulty': 4,
        'pattern_type': 'rotation_sequence',
        'layout': 'linear_sequence',
        'title': 'Clockwise Compass Turning',
        'prompt': 'The pointer turns clockwise by a quarter-turn at each step: Up, Right, Down. Which direction points next?',
        'sequence': [
            {'tile_id': 'pointer_up', 'name': 'Pointer Up', 'svg': make_pointer(0)},
            {'tile_id': 'pointer_right', 'name': 'Pointer Right', 'svg': make_pointer(90)},
            {'tile_id': 'pointer_down', 'name': 'Pointer Down', 'svg': make_pointer(180)},
            {'is_missing': True, 'position': 4},
        ],
        'target_tile': {
            'id': 'pointer_left',
            'name': 'Pointer Left',
            'svg': make_pointer(270),
        },
        'distractors': [
            {'id': 'pointer_up', 'name': 'Pointer Up', 'svg': make_pointer(0)},
            {'id': 'pointer_right', 'name': 'Pointer Right', 'svg': make_pointer(90)},
            {'id': 'pointer_down', 'name': 'Pointer Down', 'svg': make_pointer(180)},
            {'id': 'pointer_diag', 'name': 'Pointer Diagonal', 'svg': make_pointer(45)},
        ],
        'explanation': 'The pointer rotates 90 degrees clockwise each turn (Up, Right, Down). The next quarter-turn points to the Left.',
    },

    'lvl4_crescent_rotation': {
        'puzzle_id': 'lvl4_crescent_rotation',
        'difficulty': 4,
        'pattern_type': 'rotation_sequence',
        'layout': 'linear_sequence',
        'title': 'Turning Golden Crescent',
        'prompt': 'The curved crescent turns clockwise step by step. Which crescent shows the next quarter turn?',
        'sequence': [
            {'tile_id': 'cres_up', 'name': 'Crescent Opening Up', 'svg': make_crescent(0)},
            {'tile_id': 'cres_right', 'name': 'Crescent Opening Right', 'svg': make_crescent(90)},
            {'tile_id': 'cres_down', 'name': 'Crescent Opening Down', 'svg': make_crescent(180)},
            {'is_missing': True, 'position': 4},
        ],
        'target_tile': {
            'id': 'cres_left',
            'name': 'Crescent Opening Left',
            'svg': make_crescent(270),
        },
        'distractors': [
            {'id': 'cres_up', 'name': 'Crescent Opening Up', 'svg': make_crescent(0)},
            {'id': 'cres_right', 'name': 'Crescent Opening Right', 'svg': make_crescent(90)},
            {'id': 'cres_down', 'name': 'Crescent Opening Down', 'svg': make_crescent(180)},
            {'id': 'cir_full', 'name': 'Full Moon Circle', 'svg': make_circle('#FEF3C7', '#D97706')},
        ],
        'explanation': 'The crescent opening rotates clockwise by 90 degrees each step. Following the downward opening is the Crescent Opening Left.',
    },

    'lvl4_symmetric_reflection': {
        'puzzle_id': 'lvl4_symmetric_reflection',
        'difficulty': 4,
        'pattern_type': 'symmetry_reflection',
        'layout': 'matrix_2x2',
        'title': 'Mirror Reflection Symmetry',
        'prompt': 'Shapes mirror each other across the columns. What mirrors the left-pointing curved feather?',
        'matrix': [
            [
                {'tile_id': 'feather_left', 'name': 'Left Feather', 'svg': make_feather(False)},
                {'tile_id': 'feather_right', 'name': 'Right Feather', 'svg': make_feather(True)},
            ],
            [
                {'tile_id': 'feather_left_terracotta', 'name': 'Left Terracotta Feather', 'svg': make_feather(False, '#C2410C', '#FFEDD5')},
                {'is_missing': True, 'position': 4},
            ],
        ],
        'target_tile': {
            'id': 'feather_right_terracotta',
            'name': 'Right Terracotta Feather',
            'svg': make_feather(True, '#C2410C', '#FFEDD5'),
        },
        'distractors': [
            {'id': 'feather_left_terracotta', 'name': 'Left Terracotta Feather', 'svg': make_feather(False, '#C2410C', '#FFEDD5')},
            {'id': 'feather_right', 'name': 'Right Teal Feather', 'svg': make_feather(True)},
            {'id': 'feather_left', 'name': 'Left Teal Feather', 'svg': make_feather(False)},
            {'id': 'pointer_right', 'name': 'Pointer Right', 'svg': make_pointer(90)},
        ],
        'explanation': 'Each row consists of a left-facing motif mirrored into a right-facing motif of the same color. The answer is Right Terracotta Feather.',
    },

    'lvl4_pinwheel_quadrant': {
        'puzzle_id': 'lvl4_pinwheel_quadrant',
        'difficulty': 4,
        'pattern_type': 'rotation_sequence',
        'layout': 'linear_sequence',
        'title': 'Four-Petal Clockwise Shift',
        'prompt': 'The golden petal moves clockwise: Top, Right, Bottom. Where does it light up next?',
        'sequence': [
            {'tile_id': 'pin_top', 'name': 'Top Petal Highlighted', 'svg': make_pinwheel_quadrant('top')},
            {'tile_id': 'pin_right', 'name': 'Right Petal Highlighted', 'svg': make_pinwheel_quadrant('right')},
            {'tile_id': 'pin_bottom', 'name': 'Bottom Petal Highlighted', 'svg': make_pinwheel_quadrant('bottom')},
            {'is_missing': True, 'position': 4},
        ],
        'target_tile': {
            'id': 'pin_left',
            'name': 'Left Petal Highlighted',
            'svg': make_pinwheel_quadrant('left'),
        },
        'distractors': [
            {'id': 'pin_top', 'name': 'Top Petal Highlighted', 'svg': make_pinwheel_quadrant('top')},
            {'id': 'pin_right', 'name': 'Right Petal Highlighted', 'svg': make_pinwheel_quadrant('right')},
            {'id': 'pin_bottom', 'name': 'Bottom Petal Highlighted', 'svg': make_pinwheel_quadrant('bottom')},
            {'id': 'pin_all', 'name': 'All Petals Highlighted', 'svg': make_pinwheel_quadrant('all')},
        ],
        'explanation': 'The golden petal advances clockwise around the 4 petals (Top, Right, Bottom). The fourth position highlights the Left Petal.',
    },

    'lvl4_diamond_tilt_alternate': {
        'puzzle_id': 'lvl4_diamond_tilt_alternate',
        'difficulty': 4,
        'pattern_type': 'linear_alternating',
        'layout': 'linear_sequence',
        'title': 'Kolam Diamond Tilt Rhythm',
        'prompt': 'The square alternates between upright and a 45-degree diamond tilt. Which orientation comes next?',
        'sequence': [
            {'tile_id': 'sq_upright', 'name': 'Upright Square', 'svg': make_square('#CCFBF1', '#0F766E')},
            {'tile_id': 'dia_tilted', 'name': 'Tilted Diamond', 'svg': make_diamond('#CCFBF1', '#0F766E')},
            {'tile_id': 'sq_upright', 'name': 'Upright Square', 'svg': make_square('#CCFBF1', '#0F766E')},
            {'is_missing': True, 'position': 4},
        ],
        'target_tile': {
            'id': 'dia_tilted',
            'name': 'Tilted Diamond',
            'svg': make_diamond('#CCFBF1', '#0F766E'),
        },
        'distractors': [
            {'id': 'sq_upright', 'name': 'Upright Square', 'svg': make_square('#CCFBF1', '#0F766E')},
            {'id': 'tri_teal', 'name': 'Teal Triangle', 'svg': make_triangle('#CCFBF1', '#0F766E')},
            {'id': 'cir_teal', 'name': 'Teal Circle', 'svg': make_circle('#CCFBF1', '#0F766E')},
            {'id': 'cross_teal', 'name': 'Teal Cross', 'svg': make_cross('#CCFBF1', '#0F766E')},
        ],
        'explanation': 'The motif alternates between an upright square and a 45-degree tilted diamond. After the upright square comes the Tilted Diamond.',
    },

    # -------------------------------------------------------------
    # LEVEL 5: Dual Attributes & Composite Transformations (6 choices)
    # -------------------------------------------------------------
    'lvl5_dual_attr_shape_count': {
        'puzzle_id': 'lvl5_dual_attr_shape_count',
        'difficulty': 5,
        'pattern_type': 'dual_attribute_matrix',
        'layout': 'matrix_2x2',
        'title': 'Motif & Count Matrix',
        'prompt': 'Rows set the motif (Sun vs. Star); columns set the count (1 item vs. 2 items). What completes the corner?',
        'matrix': [
            [
                {'tile_id': 'sun_1', 'name': '1 Golden Sun', 'svg': make_sun('#F59E0B', '#B45309', '#D97706')},
                {'tile_id': 'sun_2', 'name': '2 Golden Suns', 'svg': f'''<svg viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg" role="img">
  <circle cx="20" cy="32" r="10" fill="#F59E0B" stroke="#B45309" stroke-width="2"/>
  <circle cx="44" cy="32" r="10" fill="#F59E0B" stroke="#B45309" stroke-width="2"/>
</svg>'''},
            ],
            [
                {'tile_id': 'star_1', 'name': '1 Amber Star', 'svg': make_count_stars(1)},
                {'is_missing': True, 'position': 4},
            ],
        ],
        'target_tile': {
            'id': 'star_2',
            'name': '2 Amber Stars',
            'svg': make_count_stars(2),
        },
        'distractors': [
            {'id': 'star_1', 'name': '1 Amber Star', 'svg': make_count_stars(1)},
            {'id': 'sun_2', 'name': '2 Golden Suns', 'svg': f'''<svg viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg" role="img">
  <circle cx="20" cy="32" r="10" fill="#F59E0B" stroke="#B45309" stroke-width="2"/>
  <circle cx="44" cy="32" r="10" fill="#F59E0B" stroke="#B45309" stroke-width="2"/>
</svg>'''},
            {'id': 'star_3', 'name': '3 Amber Stars', 'svg': make_count_stars(3)},
            {'id': 'sun_1', 'name': '1 Golden Sun', 'svg': make_sun('#F59E0B', '#B45309', '#D97706')},
            {'id': 'cir_2', 'name': '2 Teal Circles', 'svg': f'''<svg viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg" role="img">
  <circle cx="20" cy="32" r="10" fill="#CCFBF1" stroke="#0F766E" stroke-width="2"/>
  <circle cx="44" cy="32" r="10" fill="#CCFBF1" stroke="#0F766E" stroke-width="2"/>
</svg>'''},
        ],
        'explanation': 'Row 2 requires stars, and Column 2 requires a pair of items (count of 2). The matching combination is 2 Amber Stars.',
    },

    'lvl5_concentric_frame_core': {
        'puzzle_id': 'lvl5_concentric_frame_core',
        'difficulty': 5,
        'pattern_type': 'dual_attribute_matrix',
        'layout': 'matrix_2x2',
        'title': 'Frame & Core Synthesis',
        'prompt': 'The outer frame is set by the row; the inner symbol is set by the column. What belongs in the lower corner?',
        'matrix': [
            [
                {'tile_id': 'cir_dot', 'name': 'Circle with Inner Dot', 'svg': make_circle('#CCFBF1', '#0F766E', 2.5, 22, 32, 32, '<circle cx="32" cy="32" r="6" fill="#0F766E"/>')},
                {'tile_id': 'cir_star', 'name': 'Circle with Inner Star', 'svg': make_circle('#CCFBF1', '#0F766E', 2.5, 22, 32, 32, '<polygon points="32,24 34,29 39,29 35,32 37,37 32,34 27,37 29,32 25,29 30,29" fill="#0F766E"/>')},
            ],
            [
                {'tile_id': 'sq_dot', 'name': 'Square with Inner Dot', 'svg': make_square('#CCFBF1', '#0F766E', 2.5, 12, 12, 40, 40, 4, '<circle cx="32" cy="32" r="6" fill="#0F766E"/>')},
                {'is_missing': True, 'position': 4},
            ],
        ],
        'target_tile': {
            'id': 'sq_star',
            'name': 'Square with Inner Star',
            'svg': make_square('#CCFBF1', '#0F766E', 2.5, 12, 12, 40, 40, 4, '<polygon points="32,24 34,29 39,29 35,32 37,37 32,34 27,37 29,32 25,29 30,29" fill="#0F766E"/>'),
        },
        'distractors': [
            {'id': 'sq_dot', 'name': 'Square with Inner Dot', 'svg': make_square('#CCFBF1', '#0F766E', 2.5, 12, 12, 40, 40, 4, '<circle cx="32" cy="32" r="6" fill="#0F766E"/>')},
            {'id': 'cir_star', 'name': 'Circle with Inner Star', 'svg': make_circle('#CCFBF1', '#0F766E', 2.5, 22, 32, 32, '<polygon points="32,24 34,29 39,29 35,32 37,37 32,34 27,37 29,32 25,29 30,29" fill="#0F766E"/>')},
            {'id': 'cir_dot', 'name': 'Circle with Inner Dot', 'svg': make_circle('#CCFBF1', '#0F766E', 2.5, 22, 32, 32, '<circle cx="32" cy="32" r="6" fill="#0F766E"/>')},
            {'id': 'sq_cross', 'name': 'Square with Inner Cross', 'svg': make_square('#CCFBF1', '#0F766E', 2.5, 12, 12, 40, 40, 4, '<line x1="26" y1="32" x2="38" y2="32" stroke="#0F766E" stroke-width="3"/><line x1="32" y1="26" x2="32" y2="38" stroke="#0F766E" stroke-width="3"/>')},
            {'id': 'dia_star', 'name': 'Diamond with Inner Star', 'svg': make_diamond('#CCFBF1', '#0F766E', 2.5, '<polygon points="32,24 34,29 39,29 35,32 37,37 32,34 27,37 29,32 25,29 30,29" fill="#0F766E"/>')},
        ],
        'explanation': 'Row 2 uses square frames, and Column 2 uses inner stars. The synthesis is the Square with Inner Star.',
    },

    'lvl5_color_inversion_analogy': {
        'puzzle_id': 'lvl5_color_inversion_analogy',
        'difficulty': 5,
        'pattern_type': 'dual_attribute_matrix',
        'layout': 'matrix_2x2',
        'title': 'Color Inversion Analogy',
        'prompt': 'Examine the color exchange across the top row. What happens when the diamond colors exchange?',
        'matrix': [
            [
                {'tile_id': 'ring_t_dot_a', 'name': 'Teal Ring with Amber Dot', 'svg': make_circle('#CCFBF1', '#0F766E', 2.5, 22, 32, 32, '<circle cx="32" cy="32" r="8" fill="#F59E0B" stroke="#B45309" stroke-width="1.5"/>')},
                {'tile_id': 'ring_a_dot_t', 'name': 'Amber Ring with Teal Dot', 'svg': make_circle('#FEF3C7', '#D97706', 2.5, 22, 32, 32, '<circle cx="32" cy="32" r="8" fill="#0F766E" stroke="#042F2E" stroke-width="1.5"/>')},
            ],
            [
                {'tile_id': 'dia_t_dot_a', 'name': 'Teal Diamond with Amber Dot', 'svg': make_diamond('#CCFBF1', '#0F766E', 2.5, '<circle cx="32" cy="32" r="8" fill="#F59E0B" stroke="#B45309" stroke-width="1.5"/>')},
                {'is_missing': True, 'position': 4},
            ],
        ],
        'target_tile': {
            'id': 'dia_a_dot_t',
            'name': 'Amber Diamond with Teal Dot',
            'svg': make_diamond('#FEF3C7', '#D97706', 2.5, '<circle cx="32" cy="32" r="8" fill="#0F766E" stroke="#042F2E" stroke-width="1.5"/>'),
        },
        'distractors': [
            {'id': 'dia_t_dot_a', 'name': 'Teal Diamond with Amber Dot', 'svg': make_diamond('#CCFBF1', '#0F766E', 2.5, '<circle cx="32" cy="32" r="8" fill="#F59E0B" stroke="#B45309" stroke-width="1.5"/>')},
            {'id': 'ring_a_dot_t', 'name': 'Amber Ring with Teal Dot', 'svg': make_circle('#FEF3C7', '#D97706', 2.5, 22, 32, 32, '<circle cx="32" cy="32" r="8" fill="#0F766E" stroke="#042F2E" stroke-width="1.5"/>')},
            {'id': 'dia_a_dot_a', 'name': 'Amber Diamond with Amber Dot', 'svg': make_diamond('#FEF3C7', '#D97706', 2.5, '<circle cx="32" cy="32" r="8" fill="#F59E0B" stroke="#B45309" stroke-width="1.5"/>')},
            {'id': 'dia_t_dot_t', 'name': 'Teal Diamond with Teal Dot', 'svg': make_diamond('#CCFBF1', '#0F766E', 2.5, '<circle cx="32" cy="32" r="8" fill="#0F766E" stroke="#042F2E" stroke-width="1.5"/>')},
            {'id': 'dia_indigo_dot_rose', 'name': 'Indigo Diamond with Rose Dot', 'svg': make_diamond('#EEF2FF', '#4338CA', 2.5, '<circle cx="32" cy="32" r="8" fill="#BE185D" stroke="#831843" stroke-width="1.5"/>')},
        ],
        'explanation': 'Across each row, the outer color and inner dot color swap places. The Teal Diamond with Amber Dot swaps into an Amber Diamond with Teal Dot.',
    },

    'lvl5_geometric_overlay': {
        'puzzle_id': 'lvl5_geometric_overlay',
        'difficulty': 5,
        'pattern_type': 'dual_attribute_matrix',
        'layout': 'matrix_2x2',
        'title': 'Motif Overlay Combination',
        'prompt': 'Column 1 shows a base shape; Column 2 adds a horizontal crossbar. Which tile completes the triangle row?',
        'matrix': [
            [
                {'tile_id': 'cir_base', 'name': 'Plain Circle', 'svg': make_circle('#CCFBF1', '#0F766E')},
                {'tile_id': 'cir_bar', 'name': 'Circle with Crossbar', 'svg': make_shape_with_bar('circle')},
            ],
            [
                {'tile_id': 'tri_base', 'name': 'Plain Triangle', 'svg': make_triangle('#CCFBF1', '#0F766E')},
                {'is_missing': True, 'position': 4},
            ],
        ],
        'target_tile': {
            'id': 'tri_bar',
            'name': 'Triangle with Crossbar',
            'svg': make_shape_with_bar('triangle'),
        },
        'distractors': [
            {'id': 'tri_base', 'name': 'Plain Triangle', 'svg': make_triangle('#CCFBF1', '#0F766E')},
            {'id': 'cir_bar', 'name': 'Circle with Crossbar', 'svg': make_shape_with_bar('circle')},
            {'id': 'sq_bar', 'name': 'Square with Crossbar', 'svg': make_shape_with_bar('square')},
            {'id': 'tri_dot', 'name': 'Triangle with Dot', 'svg': make_triangle('#CCFBF1', '#0F766E', 2.5, '<circle cx="32" cy="34" r="6" fill="#0F766E"/>')},
            {'id': 'tri_solid', 'name': 'Solid Triangle', 'svg': make_triangle('#0F766E', '#0F766E')},
        ],
        'explanation': 'Across each row, a horizontal crossbar is layered across the base shape. Triangle plus crossbar produces Triangle with Crossbar.',
    },

    'lvl5_triple_rhythm_harmony': {
        'puzzle_id': 'lvl5_triple_rhythm_harmony',
        'difficulty': 5,
        'pattern_type': 'linear_alternating',
        'layout': 'linear_sequence',
        'title': 'Triple Attribute Alternation',
        'prompt': 'Notice the synchronized changes: Size (Large, Small), Color (Teal, Amber), and Shape (Circle, Square). What follows the Large Teal Circle?',
        'sequence': [
            {'tile_id': 'cir_lg_teal', 'name': 'Large Teal Circle', 'svg': make_circle('#CCFBF1', '#0F766E', 3, 24)},
            {'tile_id': 'sq_sm_amber', 'name': 'Small Amber Square', 'svg': make_square('#FEF3C7', '#D97706', 2.5, 20, 20, 24, 24, 3)},
            {'tile_id': 'cir_lg_teal', 'name': 'Large Teal Circle', 'svg': make_circle('#CCFBF1', '#0F766E', 3, 24)},
            {'is_missing': True, 'position': 4},
        ],
        'target_tile': {
            'id': 'sq_sm_amber',
            'name': 'Small Amber Square',
            'svg': make_square('#FEF3C7', '#D97706', 2.5, 20, 20, 24, 24, 3),
        },
        'distractors': [
            {'id': 'cir_lg_teal', 'name': 'Large Teal Circle', 'svg': make_circle('#CCFBF1', '#0F766E', 3, 24)},
            {'id': 'sq_lg_amber', 'name': 'Large Amber Square', 'svg': make_square('#FEF3C7', '#D97706', 3, 12, 12, 40, 40, 4)},
            {'id': 'sq_sm_teal', 'name': 'Small Teal Square', 'svg': make_square('#CCFBF1', '#0F766E', 2.5, 20, 20, 24, 24, 3)},
            {'id': 'cir_sm_amber', 'name': 'Small Amber Circle', 'svg': make_circle('#FEF3C7', '#D97706', 2.5, 14)},
            {'id': 'cir_lg_amber', 'name': 'Large Amber Circle', 'svg': make_circle('#FEF3C7', '#D97706', 3, 24)},
        ],
        'explanation': 'The pattern synchronizes Size, Color, and Shape in alternation. Following the Large Teal Circle comes the Small Amber Square.',
    },
}


class PatternDetectiveEngine:
    """
    Game Engine for Pattern Detective (Abstract Reasoning & Visual-Spatial Logic).
    Elder-friendly visual pattern recognition activity completing harmonious geometric
    and cultural pattern sequences with deterministic generation across 5 difficulty levels.
    """
    SLUG = 'pattern-detective'
    TOTAL_ROUNDS = 3
    TOTAL_MAX_SCORE = 3
    TEMPLATE_NAME = 'games/pattern_detective.html'

    CHOICE_COUNTS = {
        1: 3,
        2: 4,
        3: 4,
        4: 5,
        5: 6,
    }

    @classmethod
    def get_instructions(cls):
        """
        Elder-friendly step-by-step instructions for the Pattern Detective intro screen.
        """
        return [
            {
                'number': 1,
                'title': "Observe the Visual Pattern",
                'description': "Look at the harmonious sequence of symbols or grid on the main display card.",
            },
            {
                'number': 2,
                'title': "Identify the Missing Position",
                'description': "Notice the empty space marked with a question card. Consider which symbol naturally belongs there.",
            },
            {
                'number': 3,
                'title': "Select Your Choice",
                'description': "Tap the symbol card that fits best. You can change your choice anytime without penalty.",
            },
            {
                'number': 4,
                'title': "Confirm & Enjoy Feedback",
                'description': "Press \"Confirm My Selection\" to review your choice and complete 3 pleasant rounds.",
            },
        ]

    @classmethod
    def get_session_plan(cls, session=None, difficulty=1):
        """
        Deterministically plans 3 rounds for a session.
        Uses session ID and difficulty as seed so results are reproducible.
        Ensures 3 distinct puzzles across rounds.
        """
        if session and hasattr(session, 'difficulty'):
            diff = session.difficulty
        else:
            diff = difficulty

        diff = max(1, min(5, diff))
        s_id = session.id if (session and session.id) else 1
        base_seed = s_id * 1000 + diff * 10
        rng_session = random.Random(base_seed)

        diff_keys = sorted([k for k, v in PATTERN_DETECTIVE_CATALOG.items() if v['difficulty'] == diff])
        chosen_keys = rng_session.sample(diff_keys, cls.TOTAL_ROUNDS)

        plan = {}
        for r in range(1, cls.TOTAL_ROUNDS + 1):
            p_key = chosen_keys[r - 1]
            puzzle = PATTERN_DETECTIVE_CATALOG[p_key]
            target_tile = puzzle['target_tile']
            target_id = target_tile['id']
            distractors = puzzle['distractors']

            choices = [target_tile] + distractors
            rng_round = random.Random(base_seed + r)
            rng_round.shuffle(choices)

            plan[r] = {
                'puzzle_id': p_key,
                'difficulty': diff,
                'pattern_type': puzzle['pattern_type'],
                'layout': puzzle['layout'],
                'title': puzzle['title'],
                'prompt': puzzle['prompt'],
                'sequence': puzzle.get('sequence', []),
                'matrix': puzzle.get('matrix', []),
                'target_tile_id': target_id,
                'target_tile': target_tile,
                'target_ids': [target_id],
                'distractor_tile_ids': [d['id'] for d in distractors],
                'choices': choices,
                'choice_tile_ids': [c['id'] for c in choices],
                'choice_ids': [c['id'] for c in choices],
                'explanation': puzzle['explanation'],
            }
        return plan

    @classmethod
    def get_round_data(cls, round_number, session=None):
        if round_number not in (1, 2, 3):
            raise ValueError(f"Invalid round number {round_number}. Max rounds is {cls.TOTAL_ROUNDS}.")

        plan = cls.get_session_plan(session=session)
        round_plan = dict(plan[round_number])
        round_plan['round_number'] = round_number
        round_plan['total_rounds'] = cls.TOTAL_ROUNDS
        return round_plan

    @classmethod
    def evaluate_round(cls, round_number, actual_selected_ids, response_time_ms, session=None):
        if round_number not in (1, 2, 3):
            raise ValueError(f"Invalid round number {round_number}.")

        round_data = cls.get_round_data(round_number, session=session)
        target_id = round_data['target_ids'][0]
        target_name = round_data['target_tile']['name']
        explanation = round_data['explanation']

        norm_selected = [str(x) for x in actual_selected_ids]
        is_correct = (len(norm_selected) == 1 and norm_selected[0] == target_id)

        if is_correct:
            correct_ids = [target_id]
            distractor_ids = []
            missed_ids = []
            mistake_count = 0
            score = 1
            feedback_message = f"Splendid! {explanation}"
            feedback_tone = "success"
        else:
            correct_ids = []
            distractor_ids = norm_selected
            missed_ids = [target_id]
            mistake_count = 1
            score = 0
            feedback_message = f"Good effort! The harmonious choice is {target_name}. {explanation}"
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
            'explanation': explanation,
            'feedback_message': feedback_message,
            'feedback_tone': feedback_tone,
        }


# Global registry of game engines for modular expansion
GAME_ENGINES = {
    MemoryMarketEngine.SLUG: MemoryMarketEngine,
    DailyLifeJourneyEngine.SLUG: DailyLifeJourneyEngine,
    FamiliarFacesEngine.SLUG: FamiliarFacesEngine,
    FocusFinderEngine.SLUG: FocusFinderEngine,
    WordConnectionsEngine.SLUG: WordConnectionsEngine,
    PatternDetectiveEngine.SLUG: PatternDetectiveEngine,
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
    elif session.game.slug == 'word-connections':
        stimulus_payload = {
            'scenario_id': round_data.get('scenario_id', ''),
            'target_word_id': round_data.get('target_word_id', ''),
            'distractor_word_ids': round_data.get('distractor_ids', []),
            'choice_word_ids': round_data.get('choice_ids', []),
        }
    elif session.game.slug == 'pattern-detective':
        stimulus_payload = {
            'puzzle_id': round_data.get('puzzle_id', ''),
            'pattern_type': round_data.get('pattern_type', ''),
            'target_tile_id': round_data.get('target_tile_id', ''),
            'distractor_tile_ids': round_data.get('distractor_tile_ids', []),
            'choice_tile_ids': round_data.get('choice_tile_ids', []),
            'grid_layout': round_data.get('layout', 'linear_sequence'),
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
