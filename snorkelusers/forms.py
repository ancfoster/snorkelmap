from django import forms
from allauth.account.forms import SignupForm, LoginForm
from turnstile.fields import TurnstileField

class CustomSignupForm(SignupForm):
    first_name = forms.CharField(
        label="What should we call you?",
        required=True,
        widget=forms.TextInput(attrs={'placeholder': 'Enter your first name'})
    )
    accepted_terms_conditions = forms.BooleanField(
        required=True,
        label='I accept the terms and conditions.',
        widget=forms.CheckboxInput()
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['password1'].help_text = None
        self.fields['password1'].label = 'Password'
        self.fields['password2'].label = 'Confirm Password'
        self.fields['email'].label = 'Email'
        self.fields['username'].label = 'Create a username (publicly displayed)'
        self.fields.move_to_end('accepted_terms_conditions')

        for field in self.fields.values():
                field.widget.attrs['autocomplete'] = 'off'

    def save(self, request):
        user = super().save(request)
        user.first_name = self.cleaned_data['first_name']
        user.accepted_terms_conditions = self.cleaned_data['accepted_terms_conditions']
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