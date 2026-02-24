from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib import messages
from django.core.files.storage import FileSystemStorage
from django.core.mail import EmailMultiAlternatives
from django.conf import settings
from django.forms.models import model_to_dict
from django.http import FileResponse, Http404, HttpResponse, JsonResponse, HttpResponseNotAllowed, HttpResponseBadRequest
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.views.decorators.csrf import csrf_exempt
from .models import *
import requests
import json
import os
import re
from django.views.decorators.http import require_GET, require_POST
from .bestys_api import *
from django.db import transaction
import uuid
import traceback

def home(request):
    product_id = request.session.get("product_id")
    if not request.user.is_authenticated:
        return redirect('login_user')
    
    if not product_id:
        messages.warning(request, "Сначала выберите продукт")
        return redirect("products")
    
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
                "id", "participant_id", "user_id", "first_name", "last_name", "email",
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

def normalize_kz_phone(raw):
    digits = re.sub(r"\D", "", raw or "")
    if len(digits) == 11 and digits.startswith("77"):
        return digits
    if len(digits) == 11 and digits.startswith("87"):
        return "7" + digits[1:]
    if len(digits) == 10 and digits.startswith("7"):
        return "7" + digits
    return None

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
                    
                    phone = normalize_kz_phone(phone)
                    if not phone:
                        continue

                    phone_numbers.append(phone)
                except Client.DoesNotExist:
                    continue

            request.session['phone_numbers'] = phone_numbers  
            print(phone_numbers) 
            
            return JsonResponse({'status': 'success', 'message': 'Data received successfully'})
        
        except json.JSONDecodeError:
            return JsonResponse({'status': 'error', 'message': 'Invalid JSON data'}, status=400)
    return JsonResponse({'status': 'error', 'message': 'Invalid request method'}, status=400)


def get_emails(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            
            checked_clients = data.get('checkedClients', [])
            emails = []
            print(f"Checked clients: {checked_clients}")

            for client_id in checked_clients:
                try:
                    client = Client.objects.get(id=client_id)
                    email = client.email
            
                    if not email:
                        continue

                    emails.append(email)
                except Client.DoesNotExist:
                    continue

            request.session['emails'] = emails  
            print(emails) 
            
            return JsonResponse({'status': 'success', 'message': 'Data received successfully'})
        
        except json.JSONDecodeError:
            return JsonResponse({'status': 'error', 'message': 'Invalid JSON data'}, status=400)
    return JsonResponse({'status': 'error', 'message': 'Invalid request method'}, status=400)

def send_one_whatsapp(request):
    if request.method != "POST":
        return JsonResponse({"error": "Invalid method"}, status=405)
    
    WhatsAppAccount = get_WhatsAppAccount(request)
    if WhatsAppAccount == None:
        return JsonResponse({"error": "WhatsAppAccount is not connected"}, status=400)
    
    idInstance = WhatsAppAccount['idInstance']
    apiTokenInstance = WhatsAppAccount['apiTokenInstance']

    phone = request.POST.get("number")
    wa_text = request.POST.get("waText")
    file = request.FILES.get("file")

    if not phone or not wa_text:
        return JsonResponse({"error": "Missing data"}, status=400)

    try:
        if file:
            return send_file_single(phone, wa_text, file, idInstance, apiTokenInstance)
        else:
            return send_text_single(phone, wa_text, idInstance, apiTokenInstance)
    except Exception:
        return JsonResponse({"number": phone, "status": "error"})


@csrf_exempt
def send_email(request):
    if request.method != "POST":
        return JsonResponse({"status": "error", "message": "Invalid request method"}, status=405)

    # ✅ 1) Detect content type (multipart vs json)
    content_type = (request.content_type or "").lower()

    try:
        if "multipart/form-data" in content_type:
            # FormData path
            to_email = (request.POST.get("email") or "").strip()
            html_content = request.POST.get("html") or ""
            subject = (request.POST.get("subject") or "Новое письмо | Eduverse").strip()

            # multiple attachments: <input name="attachments" multiple>
            attachments = request.FILES.getlist("attachments")

        else:
            # JSON path (backward compatible)
            raw = request.body or b"{}"
            data = json.loads(raw)

            to_email = (data.get("email") or "").strip()
            html_content = data.get("html") or ""
            subject = (data.get("subject") or "Новое письмо | Eduverse").strip()

            attachments = []  # no files in JSON
    except Exception as e:
        tb = traceback.format_exc()
        print("PARSE ERROR:", repr(e))
        print(tb)
        return JsonResponse({"status": "error", "message": "Invalid payload", "detail": repr(e)}, status=400)

    if not to_email or not html_content:
        return JsonResponse({"status": "error", "message": "Missing email or html"}, status=400)

    from_email = getattr(settings, "DEFAULT_FROM_EMAIL", None) or getattr(settings, "EMAIL_HOST_USER", None)
    if not from_email:
        return JsonResponse(
            {"status": "error", "message": "Email settings not configured (DEFAULT_FROM_EMAIL/EMAIL_HOST_USER missing)"},
            status=500,
        )

    text_content = strip_tags(html_content)

    try:
        msg = EmailMultiAlternatives(
            subject=subject,
            body=text_content,
            from_email=from_email,
            to=[to_email],
            reply_to=["support@eduverse.kz"],
        )
        msg.attach_alternative(html_content, "text/html")

        # ✅ 2) Attach files (multiple)
        total_bytes = 0
        for f in attachments:
            # Optional: limit size per file (example 10MB)
            if f.size > 10 * 1024 * 1024:
                return JsonResponse(
                    {"status": "error", "message": f"File too large: {f.name}"},
                    status=400,
                )

            total_bytes += f.size
            msg.attach(
                f.name,
                f.read(),
                getattr(f, "content_type", None) or "application/octet-stream",
            )

        # Optional: total limit (example 20MB)
        if total_bytes > 20 * 1024 * 1024:
            return JsonResponse(
                {"status": "error", "message": "Total attachments size too large"},
                status=400,
            )

        sent_count = msg.send(fail_silently=False)
        print("EMAIL SENT, count =", sent_count)

        return JsonResponse(
            {"status": "sent", "sent_count": sent_count, "attachments": len(attachments)},
            status=200,
        )

    except Exception as e:
        tb = traceback.format_exc()
        print("EMAIL SEND ERROR:", repr(e))
        print(tb)
        return JsonResponse(
            {"status": "error", "message": "Email send failed", "detail": repr(e)},
            status=500,
        )

def send_text_single(phone, wa_text, idInstance, apiTokenInstance):
    url = f"https://7103.api.greenapi.com/waInstance{idInstance}/sendMessage/{apiTokenInstance}"
    payload = {
        "chatId": f"{phone}@c.us",
        "message": wa_text
    }

    requests.post(url, json=payload, timeout=15).raise_for_status()
    return JsonResponse({"number": phone, "status": "sent"})

def send_file_single(phone, wa_text, file, idInstance, apiTokenInstance):
    url = f"https://7103.media.greenapi.com/waInstance{idInstance}/sendFileByUpload/{apiTokenInstance}"

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
    WhatsAppAccount = get_WhatsAppAccount(request)
    if WhatsAppAccount == None:
        return JsonResponse({"error": "WhatsAppAccount is not connected"}, status=400)
    
    idInstance = WhatsAppAccount['idInstance']
    apiTokenInstance = WhatsAppAccount['apiTokenInstance']
    
    data = json.loads(request.body)
    phone = data.get("phone")
    if not phone:
        return JsonResponse({"error": "Missing phone"}, status=400)

    phone = re.sub(r"[^\d]", "", phone)

    url = f"https://7103.api.greenapi.com/waInstance{idInstance}/checkWhatsapp/{apiTokenInstance}"

    payload = { "phoneNumber": phone }
    headers = { "Content-Type": "application/json" }

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=15)
        data = response.json()

        return JsonResponse({
            "number": phone,
            "exists": data.get("existsWhatsapp", False)
        })
    except Exception:
        return JsonResponse({
            "number": phone,
            "exists": False
        })

def get_WhatsAppAccount(request):
    if not request.user.is_authenticated:
        return None
    
    crm_user = CRM_User.objects.get(user=request.user)
    phone = crm_user.phone

    try:
        whatsapp = WhatsAppAccount.objects.get(phone=phone)
        idInstance = whatsapp.idInstance
        apiTokenInstance = whatsapp.apiTokenInstance
        return {'idInstance': idInstance, 'apiTokenInstance': apiTokenInstance}
    
    except WhatsAppAccount.DoesNotExist:
        return None

def products(request):
    if not request.user.is_authenticated:
        return redirect('login_user')
    
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

    try:
        data = json.loads((request.body or b"{}").decode("utf-8"))
    except json.JSONDecodeError:
        return JsonResponse({"ok": False, "error": "Invalid JSON body"}, status=400)

    competition_id = data.get("competition")
    student_ids = data.get("students") or []

    if not competition_id:
        return JsonResponse({"ok": False, "error": "competition_id is required"}, status=400)

    if not isinstance(student_ids, list):
        return JsonResponse({"ok": False, "error": "students must be a list"}, status=400)

    resp = get_results(request, competition_id)
    results = json.loads(resp.content.decode("utf-8") or "[]")

    results_by_id = {str(r.get("participantId")): r for r in results}

    resp = get_registrants(request, competition_id)
    registrants = json.loads(resp.content.decode("utf-8") or "[]")

    registrants_by_id = {str(r.get("participantId")): r for r in registrants}

    created_deals = created_clients = skipped = 0

    with transaction.atomic():
        for participant_id in student_ids:
            participant_id = str(participant_id)

            result_card = results_by_id.get(participant_id)
            registrant_card = registrants_by_id.get(participant_id)

            if not registrant_card or not result_card:
                skipped += 1
                continue

            formatted_result = (
                f"{result_card.get('product','')} - {result_card.get('quiz','')} - "
                f"{result_card.get('points','')}/{result_card.get('maxPoints','')} - "
                f"{result_card.get('award','')}\n"
            )

            raw_phone = registrant_card.get('contact') or ""
            formatted_phone = normalize_kz_phone(raw_phone)

            client = Client.objects.filter(participant_id=participant_id).first()
            if not client:
                client = Client.objects.create(
                    participant_id=participant_id,
                    user_id=registrant_card.get('userId'),
                    first_name=registrant_card.get('name', ''),
                    last_name=registrant_card.get('surname', ''),
                    email=registrant_card.get('email', ''),
                    phone=formatted_phone,
                    grade=registrant_card.get('grade', ''),
                    school=registrant_card.get('school', ''),
                    countryId=registrant_card.get('countryId'),
                )
                created_clients += 1
            elif registrant_card.get('userId') is not None and (client.user_id is None or client.user_id != registrant_card.get('userId')):
                client.user_id = registrant_card.get('userId')
                client.save(update_fields=['user_id'])

            deal = Deal.objects.filter(product=product, client=client).first()
            if deal:
                deal.result = ((deal.result or "").rstrip() + "\n" + formatted_result)
                deal.save(update_fields=["result"])
            else:
                Deal.objects.create(product=product, client=client, result=formatted_result)
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

        result = deal.result
        clientDict["result"] = result        

        clientJson = json.dumps(clientDict, default=str)  # Using default=str for unsupported type, like None
        
        context = {
            'client_id': client_id,
            'client': clientJson,
        }
        return render(request, "client.html", context)
    
@csrf_exempt  
@require_POST
def saveHTML(request):
    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return HttpResponseBadRequest("Invalid JSON")

    html = payload.get("html")
    title = payload.get("title", "") or ""

    if not isinstance(html, str) or not html.strip():
        return HttpResponseBadRequest("Field 'html' is required")

    obj = EmailTemplate.objects.create(html=html, title=title)
    return JsonResponse({"uuid": str(obj.uuid)})


def email_open(request, email_id):
    email = EmailTemplate.objects.get(uuid=email_id)
    list_of_emails = request.session.get('emails') or []
    print('LIST OF EMAILS')
    print(list_of_emails)
    context = {
        "email_html": json.dumps(email.html),
        "list_of_emails": json.dumps(list_of_emails),
    }

    return render(request, "email.html", context)