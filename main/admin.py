from datetime import date
from django.contrib import admin, messages
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.http import HttpResponse, HttpResponseRedirect
from django.urls import path, reverse
from django.core.exceptions import ValidationError
from django.template.response import TemplateResponse

from .models import Answer, Group, Question, Specialty, Student

from .forms import StudentImportForm
from .services import (
    build_import_template_xlsx,
    export_group_xlsx,
    import_students_from_xlsx,
    regenerate_password,
)

XLSX_CONTENT_TYPE = (
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
)

def download_template_view(request):
    buffer = build_import_template_xlsx()
    response = HttpResponse(buffer.getvalue(), content_type=XLSX_CONTENT_TYPE)
    response['Content-Disposition'] = (
        'attachment; filename="import_students_template.xlsx"'
    )
    return response


# Добавляем /admin/download-template/ к стандартному admin.site
_original_admin_get_urls = admin.site.get_urls


def _admin_get_urls_with_extras():
    custom = [
        path(
            'download-template/',
            admin.site.admin_view(download_template_view),
            name='main_download_students_template',
        ),
    ]
    return custom + _original_admin_get_urls()


admin.site.get_urls = _admin_get_urls_with_extras
admin.site.index_template = 'admin/custom_index.html'

User = get_user_model()


@admin.register(Specialty)
class SpecialtyAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'slug')
    search_fields = ('code', 'name', 'slug')
    readonly_fields = ('slug',)

    def get_readonly_fields(self, request, obj=None):
        if obj is None:
            return ()
        return ('slug',)


@admin.register(Group)
class GroupAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'course', 'financing', 'base', 'specialty')
    list_filter = ('course', 'financing', 'base', 'specialty')
    search_fields = ('name', 'slug')
    change_form_template = 'admin/main/group/change_form.html'

    def get_readonly_fields(self, request, obj=None):
        if obj is None:
            return ()
        return ('slug',)

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path(
                '<path:object_id>/import-students/',
                self.admin_site.admin_view(self.import_students_view),
                name='main_group_import_students',
            ),
            path(
                '<path:object_id>/export-handout/',
                self.admin_site.admin_view(self.export_handout_view),
                name='main_group_export_handout',
            ),
        ]
        return custom + urls

    def import_students_view(self, request, object_id):
        group = self.get_object(request, object_id)
        if group is None:
            return HttpResponseRedirect(reverse('admin:main_group_changelist'))

        if request.method == 'POST':
            form = StudentImportForm(request.POST, request.FILES)
            if form.is_valid():
                try:
                    count = import_students_from_xlsx(group, form.cleaned_data['file'])
                except ValidationError as exc:
                    for msg in exc.messages:
                        self.message_user(request, msg, level=messages.ERROR)
                else:
                    self.message_user(
                        request,
                        f'Импортировано студентов в группу «{group.name}»: {count}.',
                    )
                    return HttpResponseRedirect(
                        reverse('admin:main_group_change', args=[group.pk])
                    )
        else:
            form = StudentImportForm()

        context = {
            **self.admin_site.each_context(request),
            'title': f'Импорт студентов в группу «{group.name}»',
            'form': form,
            'group': group,
            'opts': self.model._meta,
        }
        return TemplateResponse(
            request, 'admin/main/group/import_students.html', context
        )
    
    def export_handout_view(self, request, object_id):
        group = self.get_object(request, object_id)
        if group is None:
            return HttpResponseRedirect(reverse('admin:main_group_changelist'))

        if not group.students.exists():
            self.message_user(
                request,
                f'В группе «{group.name}» нет студентов — раздатка будет пустой.',
                level=messages.WARNING,
            )

        buffer = export_group_xlsx(group)
        safe_slug = group.slug.replace('/', '-')
        filename = f'handout_{safe_slug}_{date.today().strftime("%Y-%m-%d")}.xlsx'
        response = HttpResponse(buffer.getvalue(), content_type=XLSX_CONTENT_TYPE)
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response


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


class AnswerInline(admin.TabularInline):
    model = Answer
    extra = 0
    fields = ('text', 'is_correct')


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ('id', 'short_text', 'specialty', 'answers_count')
    list_filter = ('specialty',)
    search_fields = ('text',)
    inlines = [AnswerInline]
    readonly_fields = ('created_at',)

    @admin.display(description='Текст')
    def short_text(self, obj):
        return obj.text[:80]

    @admin.display(description='Ответов')
    def answers_count(self, obj):
        return obj.answers.count()

