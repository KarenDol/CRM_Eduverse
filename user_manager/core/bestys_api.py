import base64
import json
import requests
from typing import Dict, Any, Optional
from urllib.parse import quote

from django.http import JsonResponse
from django.views.decorators.http import require_GET
from django.shortcuts import redirect, render

from .models import Client


BASE_URL = "https://back.bestys.co/api"
BACK_BASE_URL = "https://back.bestys.co/api"

# ---------------------------------------------------------------------
# Browser-like headers (обязательны)
# ---------------------------------------------------------------------

BASE_HEADERS: Dict[str, str] = {
    "Accept": "application/json, text/plain, */*",
    "Accept-Encoding": "gzip, deflate, br, zstd",
    "Accept-Language": "en-US,en;q=0.9,ru;q=0.8,kk;q=0.7",
    "Content-Type": "application/json",
    "Origin": "https://app.eduverse.kz",
    "Referer": "https://app.eduverse.kz/",
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/142.0.0.0 Safari/537.36"
    ),
    "Sec-Fetch-Site": "cross-site",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Dest": "empty",
    "Access-Control-Allow-Origin": "https://stemco.tech",
}

# ---------------------------------------------------------------------
# AUTH HELPERS (SESSION-BASED)
# ---------------------------------------------------------------------

def _bestys_login_impl(base_url: str, request, session_key_access: str = "bestys_access", session_key_refresh: str = "bestys_refresh") -> None:
    """Login to a bestys API (api.bestys.co or back.bestys.co). Stores tokens in request.session under given keys."""
    credentials = {
        "login": "karenadmin",
        "password": "KarenEduverse@100",
    }
    auth_b64 = base64.b64encode(
        json.dumps(credentials).encode("utf-8")
    ).decode("utf-8")

    r = requests.post(
        f"{base_url}/login",
        params={"timeOffset": 540},
        json={"auth": auth_b64},
        headers=BASE_HEADERS,
        timeout=10,
    )

    print("LOGIN STATUS:", r.status_code, base_url)
    print("LOGIN TEXT:", r.text[:200] if r.text else "")

    if r.status_code != 200:
        raise RuntimeError("Bestys login failed")

    data = r.json()
    request.session[session_key_access] = data.get("access")
    request.session[session_key_refresh] = data.get("refresh")
    if not request.session[session_key_access]:
        raise RuntimeError("Access token missing")
    request.session.modified = True


def bestys_login(request) -> None:
    """Logs into Bestys (api.bestys.co) and stores tokens in Django session."""
    _bestys_login_impl(BASE_URL, request)


def bestys_login_back(request) -> None:
    """Logs into back.bestys.co (same backend as app.eduverse.kz). Use this token for get/account/detail."""
    _bestys_login_impl(
        BACK_BASE_URL,
        request,
        session_key_access="bestys_back_access",
        session_key_refresh="bestys_back_refresh",
    )


def bestys_refresh(request) -> bool:
    """
    Refreshes access token using refresh token from session.
    """
    refresh_token = request.session.get("bestys_refresh")
    if not refresh_token:
        return False

    r = requests.get(
        f"{BASE_URL}/refresh/token",
        headers={
            **BASE_HEADERS,
            "Authorization": f"Bearer {refresh_token}",
        },
        timeout=10,
    )

    print("REFRESH STATUS:", r.status_code)
    print("REFRESH TEXT:", r.text)

    if r.status_code != 200:
        return False

    data = r.json()
    request.session["bestys_access"] = data.get("access")
    request.session.modified = True

    return True


# ---------------------------------------------------------------------
# SAFE REQUEST WRAPPER
# ---------------------------------------------------------------------

def bestys_request(
    request,
    method: str,
    path: str,
    *,
    json_body: Optional[Dict[str, Any]] = None,
    retry: bool = True,
) -> requests.Response:
    """
    Bestys API request with:
    - access token from Django session
    - refresh on 401
    - one retry max
    """
    access_token = request.session.get("bestys_access")

    if not access_token:
        bestys_login(request)
        access_token = request.session["bestys_access"]

    r = requests.request(
        method,
        f"{BASE_URL}/{path}",
        json=json_body,
        headers={
            **BASE_HEADERS,
            "Authorization": f"Bearer {access_token}",
        },
        timeout=10,
    )

    if r.status_code != 401:
        return r

    # access token expired
    if retry:
        print("401 → refreshing token")

        if bestys_refresh(request):
            return bestys_request(
                request,
                method,
                path,
                json_body=json_body,
                retry=False,
            )

        print("Refresh failed → re-login")
        bestys_login(request)

        return bestys_request(
            request,
            method,
            path,
            json_body=json_body,
            retry=False,
        )

    return r


def back_bestys_get_account_detail(request, user_id: int) -> requests.Response:
    """
    GET https://back.bestys.co/api/user/get/account/detail?userId={user_id}
    Uses bestys_back_access token (login to back.bestys.co). Returns the
    participant's token + details (same as olymp-app getAccountDetail).
    """
    bestys_login_back(request)
    access_token = request.session.get("bestys_back_access")
    if not access_token:
        raise RuntimeError("No back.bestys token")
    url = f"{BACK_BASE_URL}/user/get/account/detail"
    r = requests.get(
        url,
        params={"userId": user_id},
        headers={
            **BASE_HEADERS,
            "Authorization": f"Bearer {access_token}",
        },
        timeout=10,
    )
    print(f"get/account/detail userId={user_id} status={r.status_code} body_len={len(r.text)}")
    if r.status_code == 200 and r.text:
        try:
            resp = r.json()
            print("get/account/detail response keys:", list(resp.keys()) if isinstance(resp, dict) else "not a dict")
        except Exception:
            pass
    return r


def back_bestys_get_participant(request, participant_id: int) -> requests.Response:
    """
    GET https://back.bestys.co/api/participant/id/{participant_id}
    Uses same session token as api.bestys.co. Call this to "change the ticket"
    before redirecting user to app.eduverse.kz.
    """
    access_token = request.session.get("bestys_access")
    if not access_token:
        bestys_login(request)
        access_token = request.session["bestys_access"]

    url = f"{BACK_BASE_URL}/participant/id/{participant_id}"
    r = requests.get(
        url,
        headers={
            **BASE_HEADERS,
            "Authorization": f"Bearer {access_token}",
        },
        timeout=10,
    )
    return r


# ---------------------------------------------------------------------
# DJANGO VIEW
# ---------------------------------------------------------------------

EDUVERSE_APP_URL = "https://app.eduverse.kz"


@require_GET
def eduverse_token(request):
    """
    Get a fresh access token by logging in to back.bestys.co as karenadmin
    (same backend as app.eduverse.kz and get/account/detail). This token is
    required for GET back.bestys.co/api/user/get/account/detail?userId=...
    """
    try:
        bestys_login_back(request)
        access_token = request.session.get("bestys_back_access") or ""
        return JsonResponse({"access_token": access_token})
    except Exception as e:
        print("eduverse_token: bestys_login_back failed", e)
        return JsonResponse(
            {"error": "Login failed", "access_token": ""},
            status=502,
        )


@require_GET
def eduverse_participant_token(request, user_id: int):
    """
    Server-side: login to back.bestys.co, call get/account/detail?userId=X,
    return the participant's access token. Same flow as olymp-app ninja mode.
    Avoids CORS by doing the get/account/detail call on the server.
    """
    try:
        r = back_bestys_get_account_detail(request, user_id)
        if r.status_code != 200:
            return JsonResponse(
                {"error": "get/account/detail failed", "access_token": ""},
                status=r.status_code,
            )
        data = r.json()
        token_obj = data.get("token")
        if isinstance(token_obj, dict):
            participant_access = token_obj.get("access") or token_obj.get("accessToken") or ""
        else:
            participant_access = data.get("accessToken") or data.get("access_token") or ""
        if isinstance(participant_access, list) and participant_access:
            participant_access = participant_access[0]
        if not isinstance(participant_access, str):
            participant_access = ""
        return JsonResponse({"access_token": participant_access})
    except Exception as e:
        print("eduverse_participant_token failed", e)
        return JsonResponse(
            {"error": str(e), "access_token": ""},
            status=502,
        )


EDUVERSE_PARTICIPANT_URL = "https://app.eduverse.kz/default/participant"


@require_GET
def open_eduverse_participant(request, participant_id: int):
    """
    Serve a page that runs in the browser and:
    1. GETs /eduverse/participant-token/{user_id}/ (server does back.bestys login
       + get/account/detail, returns participant token),
    2. Redirects to app.eduverse.kz with that token in the hash.
    Uses participant_id as userId (Client.user_id was removed in migration 0013).
    """
    user_id = participant_id
    return render(
        request,
        "eduverse_redirect.html",
        {"user_id": user_id},
    )


@require_GET
def eduverse_participant_search(request):
    """
    Page with iframe (app.eduverse.kz participant list) + input for userId/participant id
    and "Load & Filter" button. User types id, clicks button → iframe loads with ?id=…
    With the Tampermonkey userscript installed, the iframe will auto-fill search and click Filter.
    Optional ?id= or path with id pre-fills the input.
    """
    initial_id = request.GET.get("id", "").strip()
    return render(
        request,
        "eduverse_participant_search.html",
        {"initial_id": initial_id, "participant_url": EDUVERSE_PARTICIPANT_URL},
    )


@require_GET
def get_competitions(request):
    base_body: Dict[str, Any] = {
        "brandId": None,
        "isAggregator": False,
        "sortDirection": "desc",
        "sortKey": "id",
        "subjectId": None,
    }

    all_competitions = []

    for is_own in (True, False):
        body = {**base_body, "isOwn": is_own}

        r = bestys_request(
            request,
            "POST",
            "product/search",
            json_body=body,
        )

        if r.status_code != 200:
            return JsonResponse(
                {"error": "Bestys API error"},
                status=r.status_code
            )

        data = r.json() or []
        all_competitions.extend(data)

    # Remove duplicates by id
    unique = {comp["id"]: comp for comp in all_competitions}

    # Filter only COMPLETED
    filtered = [
        comp for comp in unique.values()
        if comp.get("status") == "COMPLETED"
    ]

    # ✅ Sort alphabetically by name (case-insensitive)
    filtered.sort(key=lambda x: (x.get("name") or "").lower())

    return JsonResponse(filtered, safe=False)

def get_results(request, competition_id):
    body: Dict[str, Any] = {
        "sandboxId": 0,
        "countryId": 0,
        "schoolId": 0,
        "brandId": None,
        "productId": competition_id,
        "quizId": 0,
        "projectId": 0,
        "grade": 0,
        "accessId": 0,
        "type": "",
        "subjectId": 0,
        "search": "",
        "searchKey": None,
        "searchValue": None,
        "sortKey": "",
        "sortDirection": "",
        "page": 0,
        "size": 1000
    }

    r = bestys_request(
        request,
        "POST",
        "participant-quiz/search?timeOffset=300",
        json_body=body,
    )
    
    registrants = r.json()['results']

    return JsonResponse(registrants, safe=False, status=r.status_code)


#Used for the backend
def get_registrants(request, competition_id):
    body: Dict[str, Any] = {
        "productId": competition_id,
        "schoolId": None,
        "partnerId": None,
        "countryId": None,
        "levelType":"", 
        "grade": None,
        "page":0,
        "size":250,
        "idsSrc":"",
        "search": None,
        "sortKey":"",
        "sortDirection":""
    }
    
    r = bestys_request(
        request,
        "POST",
        "widget/competition/registrant",
        json_body=body,
    )
    
    registrants = r.json()['results']

    return JsonResponse(registrants, safe=False, status=r.status_code)