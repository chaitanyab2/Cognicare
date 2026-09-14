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


# Global registry of game engines for modular expansion
GAME_ENGINES = {
    MemoryMarketEngine.SLUG: MemoryMarketEngine,
    DailyLifeJourneyEngine.SLUG: DailyLifeJourneyEngine,
    FamiliarFacesEngine.SLUG: FamiliarFacesEngine,
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
