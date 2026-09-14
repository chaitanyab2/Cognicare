from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from apps.accounts.models import CustomUser, CaregiverMemberRelationship


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    list_display = ('username', 'email', 'first_name', 'last_name', 'role', 'is_active', 'is_staff')
    list_filter = ('role', 'is_active', 'is_staff')
    fieldsets = UserAdmin.fieldsets + (
        ('Cognicare Role', {'fields': ('role',)}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Cognicare Role', {'fields': ('role',)}),
    )


@admin.register(CaregiverMemberRelationship)
class CaregiverMemberRelationshipAdmin(admin.ModelAdmin):
    list_display = ('caregiver', 'member', 'is_active', 'created_at')
    list_filter = ('is_active', 'created_at')
    search_fields = ('caregiver__username', 'member__username', 'caregiver__email', 'member__email')
    raw_id_fields = ('caregiver', 'member')
