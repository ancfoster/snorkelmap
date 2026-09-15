from django.shortcuts import render

def home(request):
    return render(request, 'home.html')

def privacy_policy(request):
    return render(request, 'privacy_policy.html')

def terms_conditions(request):
    return render(request, 'terms_conditions.html')