from django import forms
from allauth.account.forms import SignupForm, LoginForm
from turnstile.fields import TurnstileField

class CustomSignupForm(SignupForm):
    first_name = forms.CharField(label="What should we call you?",required=True,widget=forms.TextInput(attrs={'placeholder': 'Enter your first name'}))
    #turnstile = TurnstileField()

    def save(self, request):
        user = super().save(request)
        user.first_name = self.cleaned_data['first_name']
        user.save()
        return user
    

class CustomLoginForm(LoginForm):
    turnstile = TurnstileField()

    class Meta:
        fields = ('login', 'password', 'turnstile')
        widgets = {
            'login': forms.TextInput(attrs={'placeholder': 'Username'}),
            'password': forms.PasswordInput(attrs={'placeholder': 'Password'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if hasattr(self.fields['password'], 'widget'):
            self.fields['password'].help_text = None

        if 'turnstile' in self.fields:
            self.fields['turnstile'].label = ''
            self.fields['turnstile'].help_text = None