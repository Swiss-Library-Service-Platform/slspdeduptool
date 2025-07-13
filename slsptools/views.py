from django.http import HttpResponse, JsonResponse, HttpRequest
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.forms import AuthenticationForm

def index(request: HttpRequest) -> HttpResponse:
    """
    Display the list of apps

    This view is unprotected and can be accessed by anyone.
    """

    # Render the template with the list of collections
    return render(request, 'slsptools/index.html')

def login_view(request):
    """Manage login of the user

    It uses the AuthenticationForm to authenticate the user.
    If the user is authenticated, it will redirect to the index page.
    """
    # We check the method of the request, post is used to send the form
    # and get is used to display the form
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)

        # We collect the data from the form and check if it's valid
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(username=username, password=password)

            # Redirection to the index page if the user is authenticated
            if user is not None:
                login(request, user)
                return redirect('index')

    return render(request, 'slsptools/login.html', {'form': AuthenticationForm()})

def logout_view(request):
    """Logout the user and redirect to the index page"""
    logout(request)
    return redirect('index')