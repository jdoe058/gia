from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.http import HttpResponseRedirect

from .models import Group, Specialty, Student
from .services import regenerate_password

User = get_user_model()


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
    list_display = (
        'login_display',
        'full_name_display',
        'group',
        'plain_password',
        'is_active_display',
    )
    list_filter = ('group', 'group__specialty')
    search_fields = ('last_name', 'first_name', 'middle_name', 'slug')
    readonly_fields = ('slug', 'plain_password')
    change_form_template = 'admin/main/student/change_form.html'

    @admin.display(description='Логин')
    def login_display(self, obj):
        return obj.login

    @admin.display(description='ФИО')
    def full_name_display(self, obj):
        return obj.full_name_short

    @admin.display(boolean=True, description='Активен')
    def is_active_display(self, obj):
        return obj.user.is_active

    def response_change(self, request, obj):
        if '_regenerate_password' in request.POST:
            new_password = regenerate_password(obj)
            self.message_user(
                request,
                f'Новый пароль для {obj.full_name_short} ({obj.login}): {new_password}',
            )
            return HttpResponseRedirect(request.path)
        return super().response_change(request, obj)


admin.site.unregister(User)


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    def get_fieldsets(self, request, obj=None):
        if obj is None:
            return super().get_fieldsets(request, obj)
        return (
            (None, {'fields': ('username',)}),
            ('Персональные данные', {'fields': ('first_name', 'last_name', 'email')}),
            ('Права', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
            ('Даты', {'fields': ('last_login', 'date_joined')}),
        )

    def has_module_permission(self, request):
        return request.user.is_superuser

    def has_view_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_add_permission(self, request):
        return request.user.is_superuser

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser

