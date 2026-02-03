from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib import messages
from django.core.files.storage import FileSystemStorage
from django.conf import settings
from django.forms.models import model_to_dict
from django.http import FileResponse, Http404, HttpResponse, JsonResponse, HttpResponseNotAllowed
from django.views.decorators.csrf import csrf_exempt
from .models import *
import requests
import json
import os
import re
from django.views.decorators.http import require_GET, require_POST
from .bestys_api import *
from django.db import transaction


def home(request):
    product_id = request.session.get("product_id")
    if not product_id:
        messages.warning(request, "Сначала выберите продукт")
        return redirect("products")
    
    if not request.user.is_authenticated:
        return redirect('login_user')
    
    deals = (
        Deal.objects
        .select_related("client")
        .filter(product_id=product_id)
        .order_by("-created_at")
    )

    # Extract clients (optional, but convenient)
    clients_data = [
        {
            **model_to_dict(d.client, fields=[
                "id", "participant_id", "first_name", "last_name", "email",
                "phone", "grade", "school", "countryId", "results", "note"
            ]),
            "status": d.status,  
        }
        for d in deals
    ]

    clients_json = json.dumps(clients_data, default=str)

    return render(request, "home.html", {
        "clients": clients_json,
    })

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
    
    phone_numbers = request.session.get('phone_numbers', [])
    phone_numbers_json = json.dumps(phone_numbers)

    context = {
        'phone_numbers': phone_numbers_json,
    }
    
    return render(request, 'whatsapp.html', context)

def get_numbers(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            
            checked_clients = data.get('checkedClients', [])
            phone_numbers = []
            print(f"Checked clients: {checked_clients}")

            for client_id in checked_clients:
                try:
                    client = Client.objects.get(id=client_id)
                    phone = client.phone

                    phone = re.sub(r'[^\d]', '', phone)  # Keeps only digits
                    phone_numbers.append(phone)
                except Client.DoesNotExist:
                    continue

            request.session['phone_numbers'] = phone_numbers  
            print(phone_numbers) 
            
            return JsonResponse({'status': 'success', 'message': 'Data received successfully'})
        
        except json.JSONDecodeError:
            return JsonResponse({'status': 'error', 'message': 'Invalid JSON data'}, status=400)
    return JsonResponse({'status': 'error', 'message': 'Invalid request method'}, status=400)

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

@require_POST
def wa_exists(request):
    data = json.loads(request.body)
    phone = data.get("phone")
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
    
def products(request):
    request.session.pop("product_id", None)
    return render(request, 'products.html')

@csrf_exempt
@require_POST
def select_product(request):
    data = json.loads(request.body or "{}")
    product_id = int(data.get("product_id"))

    request.session["product_id"] = product_id
    request.session.modified = True

    return JsonResponse({"ok": True, "redirect": "/"})

@csrf_exempt
def add_product(request):
    if request.method == "POST":
        data = json.loads(request.body)
        name = data["name"]
        Product.objects.create(name=name)
        return JsonResponse({"ok": True})
    
def search_products(request):
    products = list(
        Product.objects
        .all()
        .values('id', 'name')
    )

    for product in products:
        numb_of_clients = Deal.objects.filter(product_id=product["id"]).count()
        product['clients'] = numb_of_clients  # placeholder

    return JsonResponse(products, safe=False)

@csrf_exempt
def delete_product(request, product_id):
    if request.method != "DELETE":
        return HttpResponseNotAllowed(["DELETE"])

    product = get_object_or_404(Product, id=product_id)
    product.delete()
    return JsonResponse({"ok": True, "deleted_id": product_id})

@csrf_exempt
def edit_product(request, product_id):
    try:
        product = Product.objects.get(id=product_id)
    except Product.DoesNotExist:
        return JsonResponse(
            {"ok": False, "error": "Product not found", "product_id": product_id},
            status=404
        )
    
    data = json.loads(request.body.decode("utf-8") or "{}")
    name = (data.get("name") or "").strip()
    
    if Product.objects.exclude(id=product_id).filter(name__iexact=name).exists():
        return JsonResponse(
            {"ok": False, "error": "Product with this name already exists"},
            status=409
        )
    
    product.name = name
    product.save()

    return JsonResponse({
        "ok": True,
        "product": {
            "id": product.id,
            "name": product.name,
        }
    })

@csrf_exempt
@require_POST
def add_clients(request):
    product_id = request.session.get("product_id")
    if not product_id:
        return JsonResponse({"ok": False, "error": "No product selected in session"}, status=400)

    product = get_object_or_404(Product, id=product_id)
    
    data = json.loads(request.body.decode("utf-8") or "{}")
    competition_id = data.get("competition")
    student_ids = (data.get("students") or "")

    if not competition_id:
        return JsonResponse({"ok": False, "error": "competition_id is required"}, status=400)

    if not isinstance(student_ids, list):
        return JsonResponse({"ok": False, "error": "students must be a list"}, status=400)

    resp = get_results(request, competition_id)   
    results = json.loads(resp.content.decode("utf-8")) 

    # ✅ build fast maps with consistent string keys
    results_by_id = {
        str(r.get("participantId")): r
        for r in results
    }

    resp = get_registrants(request, competition_id)   
    registrants = json.loads(resp.content.decode("utf-8")) 

    registrants_by_id = {
        str(r.get("participantId")): r
        for r in registrants
    }

    created_deals = 0
    created_clients = 0
    skipped = 0

    with transaction.atomic():
        for participant_id in student_ids:
            participant_id = str(participant_id)

            result_card = results_by_id.get(participant_id)
            registrant_card = registrants_by_id.get(participant_id)

            if not registrant_card:
                skipped += 1
                continue

            formated_result = f"{result_card['product']} - {result_card['quiz']} - {result_card['points']}/{result_card['maxPoints']} - {result_card['award']}\n"

            client = Client.objects.filter(participant_id=participant_id).first()

            if client:
                client.results += formated_result
                client.save(update_fields=["results"])
                client_created = False
            else:
                client = Client.objects.create(
                    participant_id=participant_id,
                    first_name=registrant_card['name'],
                    last_name=registrant_card['surname'],
                    email=registrant_card['email'],
                    phone=(registrant_card.get('contact') or ""),
                    results=formated_result,
                    grade=registrant_card['grade'],
                    school=(result_card.get('contact') or ""),
                    countryId=registrant_card['countryId'],
                )
                client_created = True

            if client_created:
                created_clients += 1

            _, deal_created = Deal.objects.get_or_create(
                product=product,
                client=client,
            )
            if deal_created:
                created_deals += 1
                
    return JsonResponse({
        "ok": True,
        "product_id": product_id,
        "created_clients": created_clients,
        "created_deals": created_deals,
        "skipped": skipped,
    })

def client_card(request, client_id):
    client = get_object_or_404(Client, id=client_id)

    product_id = request.session.get("product_id")
    if not product_id:
        messages.warning(request, "Сначала выберите продукт")
        return redirect("products")
    
    product = get_object_or_404(Product, id=product_id)
    deal = get_object_or_404(Deal, client=client, product=product)

    if request.method == 'POST':
        with transaction.atomic():

            # ===== CLIENT FIELDS =====
            client.last_name = request.POST.get("last_name", "").strip()
            client.first_name = request.POST.get("first_name", "").strip()
            client.email = request.POST.get("email") or None
            client.phone = request.POST.get("phone", "")
            client.grade = request.POST.get("grade") or 0
            client.school = request.POST.get("school", "")
            client.results = request.POST.get("results", "")
            client.note = request.POST.get("note") or None

            client.save()

            # ===== STATUS (DEAL) =====
            status = request.POST.get("status", "Лид")

            deal.status = status
            deal.save()

            messages.success(request, "Карточка клиента успешно обновлена")

            return redirect("client_card", client_id=client_id)
        
    else:
        clientDict = model_to_dict(client)

        status = deal.status
        clientDict["status"] = status

        clientJson = json.dumps(clientDict, default=str)  # Using default=str for unsupported type, like None
        
        context = {
            'client_id': client_id,
            'client': clientJson,
        }
        return render(request, "client.html", context)