from django.shortcuts import render
from django.http import JsonResponse
from django_ratelimit.decorators import ratelimit
from django.views.decorators.csrf import csrf_exempt
import json

from django.contrib.auth import get_user_model
User = get_user_model()

#username check
@csrf_exempt
@ratelimit(key='ip', rate='12/m', method='POST')
def check_username_exists(request):
    """
    Takes a username as argument and checks if it is already in use.
    Used during signup process.
    """
    was_limited = getattr(request, 'limited', False)
    if was_limited:
        return JsonResponse({'error': 'Too many requests'}, status=429)
    
    try:
        data = json.loads(request.body)
        proposed_username = data.get("username", "").strip()
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    if len(proposed_username) > 0 and proposed_username.isalpha():
        username_exists = User.objects.filter(username=proposed_username).exists()
        if username_exists:
            return JsonResponse({
                'username': proposed_username,
                'available': False
            }, status=200)
        else:
            return JsonResponse({
                'username': proposed_username,
                'available': True
            }, status=200)
    else:
        return JsonResponse({'error': 'Invalid username'}, status=400)