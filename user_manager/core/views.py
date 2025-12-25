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
        return redirect('login_user', prev_page='home')
    else:
        return redirect('whatsapp')

#Login and logout with prev_page 
def login_user(request, prev_page):
    if request.user.is_authenticated:
        return redirect(prev_page)
    else:
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
                return redirect(prev_page)
            else:
                return redirect('login_user', prev_page)
        else:
            context={
                'prev_page': prev_page,
            }
            return render(request, 'login.html', context)
        
def logout_user(request, prev_page):
    logout(request)
    messages.info(request, "You have been logged out!")
    return redirect('login_user', prev_page=prev_page) 

#Fetch the name and the picture of the user for the index.html
def get_user_info(request):
    if request.user.is_authenticated:
        current_user = CRM_User.objects.get(user=request.user)
        user_info = {
            'name': current_user.name,  
            'picture': f"avatars/{current_user.picture}",
            'school': request.session['school']
        }
        return JsonResponse(user_info)
    else:
        user_info = {
            'name': 'Гость',  
            'picture': 'avatars/Avatar.png',
            'school': 'sch'
        }
        return JsonResponse(user_info) 
    
def serve_static(request, filename):
    file_path = os.path.join(settings.STATIC_ROOT, "core", filename)
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
        user_dict['position'] = User_type_dict[current_user.user_type]
        user_dict['username'] = current_user.user.username
        user_dict['picture'] = f"avatars/{user_dict['picture']}"

        context = {
            'user_dict': user_dict,
        }
        return render(request, 'user_settings.html', context)
    
def error(request, prev_page, error_code):
    context = {
        'prev_page': prev_page,
        'error_code': error_code,
    }
    return render(request, '404.html', context)

def whatsapp(request):
    if not request.user.is_authenticated:
        return redirect('login_user', prev_page='home')
    
    if request.method == "POST":
        try:
            phone_numbers = json.loads(request.POST.get('phoneNumbers', '[]'))
            wa_text = request.POST.get('waText', '')
            file = request.FILES.get('file')

            if (file):
                return send_file(phone_numbers, wa_text, file)
            else:
                return send_text(phone_numbers, wa_text)
            
        except json.JSONDecodeError:
            return JsonResponse({'status': 'error', 'message': 'Invalid JSON data'}, status=400)
    else:
        return render(request, 'whatsapp.html')
    
def send_text(phone_numbers, wa_text):
    status_dict = []

    url = "https://7103.api.greenapi.com/waInstance7103440972/sendMessage/7833fac0e9ec4bf3b114d58c87411cec62e741f5c31c452885"

    for phone in phone_numbers:
        if phone['status'] == "not-exist":
            status_dict.append(phone)
            continue                 
                                                                                                                            
        phone = phone['number']
        payload = {
            "chatId": f"{phone}@c.us",
            "message": wa_text
        }
        headers = {
            'Content-Type': 'application/json'
        }

        try:
            response = requests.post(url, json=payload, headers=headers)
            response.raise_for_status()
            result = response.json()
            status_dict.append({'number': phone, 'status': 'sent'})
        except requests.RequestException as e:
            status_dict.append({'number': phone, 'status': 'error'})

    # Return a success response
    return JsonResponse({'status': 'success', 'status_dict': status_dict})

def send_file(phone_numbers, wa_text, file):
    status_dict = []

    url = "https://7103.media.greenapi.com/waInstance7103440972/sendFileByUpload/7833fac0e9ec4bf3b114d58c87411cec62e741f5c31c452885"

    file_content = file.read()

    for phone in phone_numbers:
        if phone['status'] == "not-exist":
            status_dict.append(phone)
            continue                 
                                                                                                                            
        phone = phone['number']
        payload = {
            'chatId': f'{phone}@c.us', 
            'fileName': file.name,
            'caption': wa_text
        }
        files = {
            'file': (file.name, file_content, file.content_type)
        }

        try:
            response = requests.post(url, data=payload, files=files)
            print(response.text)
            response.raise_for_status()
            status_dict.append({'number': phone, 'status': 'sent'})
        except requests.RequestException as e:
            status_dict.append({'number': phone, 'status': 'error'})

    # Return a success response
    return JsonResponse({'status': 'success', 'status_dict': status_dict})

def wa_exists(request, phone):
    try:
        # Remove +, parentheses, and dashes from the phone number
        phone = re.sub(r'[^\d]', '', phone)  # Keeps only digits

        url = "https://7103.api.greenapi.com/waInstance7103440972/checkWhatsapp/7833fac0e9ec4bf3b114d58c87411cec62e741f5c31c452885"

        payload = { 
            "phoneNumber": phone  
        }
        headers = {
            'Content-Type': 'application/json'
        }

        response = requests.post(url, json=payload, headers=headers)

        return JsonResponse(response.json(), status = 200)
    
    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'message': 'Invalid JSON data'}, status=400)