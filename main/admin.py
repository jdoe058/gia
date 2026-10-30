from django.contrib import admin

from .models import Group, Specialty


@admin.register(Specialty)
class SpecialtyAdmin(admin.ModelAdmin):
    list_display = ('code', 'name')
    search_fields = ('code', 'name')


@admin.register(Group)
class GroupAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'course', 'financing', 'base', 'specialty')
    list_filter = ('course', 'financing', 'base', 'specialty')
    search_fields = ('name', 'slug')

    def get_readonly_fields(self, request, obj=None):
        if obj is None:
            return ()
        return ('slug',)

