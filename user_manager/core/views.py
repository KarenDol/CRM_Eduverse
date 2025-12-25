from django.shortcuts import render, redirect
from django.contrib.auth import login, logout, authenticate
from django.contrib import messages
from django.core.files.storage import FileSystemStorage
from django.conf import settings
from django.forms.models import model_to_dict
from django.http import FileResponse, Http404, HttpResponse, JsonResponse
from .models import *
import requests
import json
import os
import re

def home(request):
    if not request.user.is_authenticated:
        return redirect('login_user')
    else:
        return redirect('whatsapp')

def login_user(request):
    if request.user.is_authenticated:
        return redirect('home')
    if request.method == "POST":
        username = request.POST['username']
        password = request.POST['password']
        remember_me = request.POST.get('remember_me')
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            if remember_me:
                request.session.set_expiry(1209600)  # 2 weeks in seconds
            else:
                request.session.set_expiry(0)
            return redirect('home')
        else:
            return redirect('login_user')
    else:
        return render(request, 'login.html')
        
def logout_user(request):
    logout(request)
    messages.info(request, "You have been logged out!")
    return redirect('login_user') 

#Fetch the name and the picture of the user for the index.html
def get_user_info(request):
    if request.user.is_authenticated:
        current_user = CRM_User.objects.get(user=request.user)
        user_info = {
            'name': current_user.name,  
            'picture': f"avatars/{current_user.picture}",
        }
        return JsonResponse(user_info)
    else:
        user_info = {
            'name': 'Гость',  
            'picture': 'avatars/Avatar.png',
        }
        return JsonResponse(user_info) 
    
def serve_static(request, filename):
    file_path = os.path.join(settings.STATIC_ROOT, filename)
    print("FILE_PATH:" + file_path)
    if os.path.exists(file_path):
        return FileResponse(open(file_path, 'rb'))
    else:
        raise Http404("Avatar not found")

def user_settings(request):
    current_user = CRM_User.objects.get(user=request.user)
    if request.method == "POST":
        try:
            new_username = request.POST['username']
            if new_username and new_username != current_user.user.username:
                current_user.user.username = new_username
                current_user.user.save()
            
            oldPassword = request.POST['oldPassword']
            newPassword = request.POST['newPassword']
            if oldPassword:
                user = authenticate(username = request.user.username, password = oldPassword)
                print(request.user.username, oldPassword)
                if user is not None:
                    user.set_password(newPassword)
                    user.save()
                else:
                    print("WrongPassword")
            
            new_email = request.POST['email']
            if new_email and new_email != current_user.email:
                current_user.email = new_email
            
            new_phone = request.POST['phone']
            if new_phone and new_phone != current_user.phone:
                current_user.phone = new_phone

            if 'avatar' in request.FILES:
                new_avatar = request.FILES['avatar']
                folder_path = os.path.join(settings.STATIC_ROOT, 'user_manager', 'avatars')

                # Set the file_name
                file_name = current_user.user.username
                extension = os.path.splitext(new_avatar.name)[1]  # e.g., '.jpg'

                # Delete the file if it exists (only 1 image per user)
                if current_user.picture != "Avatar.png":
                    old_avatar = os.path.join(folder_path, current_user.picture) 
                    if os.path.isfile(old_avatar):
                        os.remove(old_avatar)

                fs = FileSystemStorage(folder_path)
                fs.save(f"{file_name}{extension}", new_avatar)

                current_user.picture = f"{file_name}{extension}"

            current_user.save()
            # Send success response
            return JsonResponse({'status': 'success', 'message': 'Settings updated successfully'}, status=200)
        except Exception as e:
            # Handle exceptions and return an error response
            print(f"Error occurred: {e}")
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
    else:
        user_dict = model_to_dict(current_user, fields=['name', 'phone', 'email', 'picture'])
        user_dict['username'] = current_user.user.username
        user_dict['picture'] = f"avatars/{user_dict['picture']}"

        context = {
            'user_dict': user_dict,
        }
        return render(request, 'user_settings.html', context)
    
def error(request, error_code):
    context = {
        'error_code': error_code,
    }
    return render(request, '404.html', context)

def whatsapp(request):
    if not request.user.is_authenticated:
        return redirect('login_user')
    
    return render(request, 'whatsapp.html')

def send_one_whatsapp(request):
    if request.method != "POST":
        return JsonResponse({"error": "Invalid method"}, status=405)

    phone = request.POST.get("number")
    wa_text = request.POST.get("waText")
    file = request.FILES.get("file")

    if not phone or not wa_text:
        return JsonResponse({"error": "Missing data"}, status=400)

    try:
        if file:
            return send_file_single(phone, wa_text, file)
        else:
            return send_text_single(phone, wa_text)
    except Exception:
        return JsonResponse({"number": phone, "status": "error"})

def send_text_single(phone, wa_text):
    url = "https://7103.api.greenapi.com/waInstance7103440972/sendMessage/7833fac0e9ec4bf3b114d58c87411cec62e741f5c31c452885"
    payload = {
        "chatId": f"{phone}@c.us",
        "message": wa_text
    }

    requests.post(url, json=payload, timeout=15).raise_for_status()
    return JsonResponse({"number": phone, "status": "sent"})

def send_file_single(phone, wa_text, file):
    url = "https://7103.media.greenapi.com/waInstance7103440972/sendFileByUpload/7833fac0e9ec4bf3b114d58c87411cec62e741f5c31c452885"

    payload = {
        "chatId": f"{phone}@c.us",
        "fileName": file.name,
        "caption": wa_text
    }

    files = {
        "file": (file.name, file.read(), file.content_type)
    }

    requests.post(url, data=payload, files=files, timeout=30).raise_for_status()
    return JsonResponse({"number": phone, "status": "sent"})

def wa_exists(request):
    if request.method != "POST":
        return JsonResponse({"error": "Invalid method"}, status=405)

    phone = request.POST.get("phone")
    if not phone:
        return JsonResponse({"error": "Missing phone"}, status=400)

    phone = re.sub(r"[^\d]", "", phone)
    print(phone)

    url = "https://7103.api.greenapi.com/waInstance7103440972/checkWhatsapp/7833fac0e9ec4bf3b114d58c87411cec62e741f5c31c452885"

    payload = { "phoneNumber": phone }
    headers = { "Content-Type": "application/json" }

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=15)
        data = response.json()
        print(data)
        return JsonResponse({
            "number": phone,
            "exists": data.get("existsWhatsapp", False)
        })
    except Exception:
        return JsonResponse({
            "number": phone,
            "exists": False
        })