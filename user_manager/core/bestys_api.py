import base64
import json
import requests
from typing import Dict, Any, Optional

from django.http import JsonResponse
from django.views.decorators.http import require_GET


BASE_URL = "https://api.bestys.co/api"

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
}

# ---------------------------------------------------------------------
# AUTH HELPERS (SESSION-BASED)
# ---------------------------------------------------------------------

def bestys_login(request) -> None:
    """
    Logs into Bestys and stores tokens in Django session.
    """
    credentials = {
        "login": "karenadmin",
        "password": "KarenEduverse@100",
    }

    auth_b64 = base64.b64encode(
        json.dumps(credentials).encode("utf-8")
    ).decode("utf-8")

    r = requests.post(
        f"{BASE_URL}/login",
        params={"timeOffset": 540},
        json={"auth": auth_b64},
        headers=BASE_HEADERS,
        timeout=10,
    )

    print("LOGIN STATUS:", r.status_code)
    print("LOGIN TEXT:", r.text)

    if r.status_code != 200:
        raise RuntimeError("Bestys login failed")

    data = r.json()

    request.session["bestys_access"] = data.get("access")
    request.session["bestys_refresh"] = data.get("refresh")

    if not request.session["bestys_access"]:
        raise RuntimeError("Access token missing")

    request.session.modified = True


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


# ---------------------------------------------------------------------
# DJANGO VIEW
# ---------------------------------------------------------------------

@require_GET
def get_competitions(request):
    body: Dict[str, Any] = {
        "brandId": None,
        "isAggregator": False,
        "isOwn": True,
        "sortDirection": "desc",
        "sortKey": "id",
        "subjectId": None,
    }

    r = bestys_request(
        request,
        "POST",
        "product/search",
        json_body=body,
    )

    #Filter only "COMPLETED" competitions
    all_competitions = r.json()
    filtered_competitions = []
    for competition in all_competitions:
        if competition['status'] == "COMPLETED":
            
            filtered_competitions.append(competition)

    return JsonResponse(filtered_competitions, safe=False, status=r.status_code)

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