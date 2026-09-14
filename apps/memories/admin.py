from django.contrib import admin
from apps.memories.models import Memory


@admin.register(Memory)
class MemoryAdmin(admin.ModelAdmin):
    list_display = ('title', 'member', 'created_at', 'updated_at')
    list_filter = ('created_at',)
    search_fields = ('title', 'description', 'member__username', 'member__email')
    raw_id_fields = ('member',)
