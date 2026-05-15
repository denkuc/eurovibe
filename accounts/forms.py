from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm

from .models import FeedbackMessage


PASSWORD_HELP_TEXT = (
    "Мінімум 15 символів. Використай унікальний пароль і збережи його. "
    "У цій версії застосунку reset, заміна або нагадування пароля недоступні."
)


class RegisterForm(UserCreationForm):
    password1 = forms.CharField(
        label="Пароль",
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
        help_text=PASSWORD_HELP_TEXT,
    )
    password2 = forms.CharField(
        label="Підтвердження пароля",
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
        help_text="Повтори той самий пароль.",
    )

    class Meta(UserCreationForm.Meta):
        fields = ("username",)
        labels = {
            "username": "Username",
        }
        help_texts = {
            "username": "Потрібен для входу. Email у v1 не використовується.",
        }


class LoginForm(AuthenticationForm):
    username = forms.CharField(
        label="Username",
        widget=forms.TextInput(attrs={"autocomplete": "username", "autofocus": True}),
    )
    password = forms.CharField(
        label="Пароль",
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "current-password"}),
        help_text="Password reset у цій версії недоступний.",
    )


class FeedbackForm(forms.ModelForm):
    class Meta:
        model = FeedbackMessage
        fields = ("name", "message")
        labels = {
            "name": "Імʼя",
            "message": "Повідомлення",
        }
        help_texts = {
            "name": "Можна залишити порожнім.",
        }
        widgets = {
            "name": forms.TextInput(attrs={"autocomplete": "name"}),
            "message": forms.Textarea(attrs={"rows": 7}),
        }
