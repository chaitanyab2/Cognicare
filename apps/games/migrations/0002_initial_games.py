from django.db import migrations


def create_initial_games(apps, schema_editor):
    Game = apps.get_model('games', 'Game')
    initial_games = [
        {
            'name': 'Memory Market',
            'slug': 'memory-market',
            'description': 'A relatable shopping basket recall game that gently exercises working memory, mental categorization, and item retention without countdown stress.',
            'display_order': 1,
            'is_active': True,
        },
        {
            'name': 'Daily Life Journey',
            'slug': 'daily-life-journey',
            'description': 'An executive function and temporal orientation activity arranging everyday sequential life tasks into proper chronological order.',
            'display_order': 2,
            'is_active': True,
        },
        {
            'name': 'Familiar Faces',
            'slug': 'familiar-faces',
            'description': 'A facial recognition and associative memory activity connecting dignified portraits with familial and personal context.',
            'display_order': 3,
            'is_active': True,
        },
        {
            'name': 'Focus Finder',
            'slug': 'focus-finder',
            'description': 'A serene visual search activity exercising selective attention and scanning in a relaxed setting without rush.',
            'display_order': 4,
            'is_active': True,
        },
        {
            'name': 'Word Connections',
            'slug': 'word-connections',
            'description': 'A semantic memory and verbal fluency activity exploring conceptual associations and meaningful words.',
            'display_order': 5,
            'is_active': True,
        },
        {
            'name': 'Pattern Detective',
            'slug': 'pattern-detective',
            'description': 'An abstract reasoning and visual-spatial logic activity completing harmonious geometric and cultural pattern sequences.',
            'display_order': 6,
            'is_active': True,
        },
    ]

    for game_data in initial_games:
        Game.objects.get_or_create(
            slug=game_data['slug'],
            defaults=game_data
        )


def remove_initial_games(apps, schema_editor):
    Game = apps.get_model('games', 'Game')
    slugs = [
        'memory-market',
        'daily-life-journey',
        'familiar-faces',
        'focus-finder',
        'word-connections',
        'pattern-detective'
    ]
    Game.objects.filter(slug__in=slugs).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('games', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(create_initial_games, reverse_code=remove_initial_games),
    ]
