from django.contrib import admin
from apps.games.models import Game, GameSession, GameRound


@admin.register(Game)
class GameAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'is_active', 'display_order', 'created_at')
    list_filter = ('is_active',)
    search_fields = ('name', 'slug', 'description')
    ordering = ('display_order', 'name')
    prepopulated_fields = {'slug': ('name',)}


class GameRoundInline(admin.TabularInline):
    model = GameRound
    extra = 0
    readonly_fields = ('round_number', 'is_correct', 'response_time_ms', 'mistake_count', 'hints_used', 'created_at')
    can_delete = False


@admin.register(GameSession)
class GameSessionAdmin(admin.ModelAdmin):
    list_display = ('id', 'member', 'game', 'status', 'difficulty', 'score', 'max_score', 'accuracy', 'started_at', 'completed_at')
    list_filter = ('status', 'difficulty', 'game', 'started_at')
    search_fields = ('member__username', 'member__email', 'game__name')
    raw_id_fields = ('member',)
    inlines = [GameRoundInline]


@admin.register(GameRound)
class GameRoundAdmin(admin.ModelAdmin):
    list_display = ('id', 'session', 'round_number', 'is_correct', 'response_time_ms', 'mistake_count', 'hints_used', 'created_at')
    list_filter = ('is_correct', 'session__game', 'created_at')
    search_fields = ('session__member__username', 'session__game__name')
    raw_id_fields = ('session',)
