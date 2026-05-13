from django import forms

from .models import FriendGroup


class FriendGroupCreateForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["includes_ukraine"].initial = False

    class Meta:
        model = FriendGroup
        fields = ["name", "includes_ukraine"]
        labels = {
            "name": "Назва групи",
            "includes_ukraine": "Голосуємо з Україною",
        }
        help_texts = {
            "name": "Можна залишити порожнім — назва створиться автоматично.",
        }


class GroupModeForm(forms.ModelForm):
    class Meta:
        model = FriendGroup
        fields = ["includes_ukraine"]
        labels = {
            "includes_ukraine": "Голосуємо з Україною",
        }


class JoinByCodeForm(forms.Form):
    join_code = forms.CharField(label="Код групи", max_length=6, min_length=6)

    def clean_join_code(self):
        return self.cleaned_data["join_code"].strip().upper()
