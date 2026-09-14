from django.contrib import admin
from apps.routines.models import Routine, RoutineItem


class RoutineItemInline(admin.TabularInline):
    model = RoutineItem
    extra = 1
    fields = ('display_order', 'title', 'scheduled_time', 'is_completed', 'completed_at')


@admin.register(Routine)
class RoutineAdmin(admin.ModelAdmin):
    list_display = ('title', 'member', 'date', 'is_active', 'item_count', 'created_at')
    list_filter = ('is_active', 'date')
    search_fields = ('title', 'description', 'member__username', 'member__email')
    raw_id_fields = ('member',)
    inlines = [RoutineItemInline]

    def item_count(self, obj):
        return obj.items.count()
    item_count.short_description = 'Items'


@admin.register(RoutineItem)
class RoutineItemAdmin(admin.ModelAdmin):
    list_display = ('title', 'routine', 'scheduled_time', 'is_completed', 'completed_at', 'display_order')
    list_filter = ('is_completed', 'scheduled_time')
    search_fields = ('title', 'description', 'routine__title', 'routine__member__username')
    raw_id_fields = ('routine',)
