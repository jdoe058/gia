from django.contrib import admin

from .models import Group, Specialty, Student


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


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ('login_display', 'full_name_display', 'group', 'plain_password')
    list_filter = ('group', 'group__specialty')
    search_fields = ('last_name', 'first_name', 'middle_name', 'slug')
    readonly_fields = ('slug', 'plain_password')

    @admin.display(description='Логин')
    def login_display(self, obj):
        return obj.login

    @admin.display(description='ФИО')
    def full_name_display(self, obj):
        return obj.full_name_short

