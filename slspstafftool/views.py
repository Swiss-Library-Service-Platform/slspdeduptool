from datetime import datetime
import ast
import json
import os

from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from pymongo import MongoClient

from almapiwrapper.config import Library


LIBRARY_STATUS_MONGO_URI_ENV = "mongodb_closed_library_automation_uri"
LIBRARY_STATUS_MONGO_DB_ENV = "mongodb_closed_library_automation_db"
LIBRARY_STATUS_MONGO_COLLECTION_ENV = "mongodb_closed_library_automation_collection"


def save_library_status_snapshot(values: dict, library_payload: dict) -> None:
    """Persist a timestamped library status snapshot into MongoDB."""
    mongo_uri = os.getenv(LIBRARY_STATUS_MONGO_URI_ENV)
    mongo_db_name = os.getenv(LIBRARY_STATUS_MONGO_DB_ENV, "closed_library_automation")
    mongo_collection_name = os.getenv(LIBRARY_STATUS_MONGO_COLLECTION_ENV, "library_closures")

    if not mongo_uri:
        raise ValueError(
            "MongoDB configuration is missing. "
            f"Set {LIBRARY_STATUS_MONGO_URI_ENV}."
        )

    client = MongoClient(mongo_uri)
    db = client[mongo_db_name]
    collection = db[mongo_collection_name]

    document = {
        "saved_at": datetime.utcnow(),
        "from_date_str": values.get("from_date_str"),
        "to_date_str": values.get("to_date_str"),
        "library_id": values.get("library_id"),
        "iz_code": values.get("iz_code"),
        "env_type": values.get("env_type"),
        "library_code": library_payload.get("code"),
        "library_name": library_payload.get("name"),
        "library_path": library_payload.get("path"),
        "opening_status": library_payload,
    }
    collection.insert_one(document)


def index(request: HttpRequest) -> HttpResponse:
    values = {
        "from_date_str": "",
        "to_date_str": "",
        "library_id": "",
        "iz_code": "",
        "env_type": "",
    }
    errors = []
    submitted = None
    library_details = None
    library_details_raw = None
    save_status_ok = False
    save_status_error = None

    if request.method == "POST":
        values = {
            "from_date_str": request.POST.get("from_date_str", "").strip(),
            "to_date_str": request.POST.get("to_date_str", "").strip(),
            "library_id": request.POST.get("library_id", "").strip(),
            "iz_code": request.POST.get("iz_code", "").strip(),
            "env_type": request.POST.get("env_type", "").strip(),
        }

        required_fields = ["from_date_str", "to_date_str", "library_id", "iz_code", "env_type"]
        for field in required_fields:
            if not values[field]:
                errors.append(f"{field} is required.")

        for date_field in ["from_date_str", "to_date_str"]:
            if values[date_field]:
                try:
                    datetime.strptime(values[date_field], "%Y-%m-%d")
                except ValueError:
                    errors.append(f"{date_field} must be in YYYY-MM-DD format.")

        if values["env_type"] and values["env_type"] not in ["S", "P", "T"]:
            errors.append("env_type must be S, P, or T.")

        if not errors:
            submitted = values.copy()
            try:
                library = Library(values["library_id"], values["iz_code"], values["env_type"])
                print(library)

                raw_data = getattr(library, "_data", None)
                if isinstance(raw_data, str):
                    try:
                        parsed = json.loads(raw_data)
                    except json.JSONDecodeError:
                        # Some client objects expose Python-literal dict strings instead of JSON.
                        try:
                            parsed = ast.literal_eval(raw_data)
                        except (ValueError, SyntaxError):
                            parsed = raw_data
                elif raw_data is not None:
                    parsed = raw_data
                else:
                    parsed = str(library)

                if not isinstance(parsed, (dict, list, str)):
                    if hasattr(parsed, "to_dict"):
                        try:
                            parsed = parsed.to_dict()
                        except Exception:
                            parsed = str(parsed)
                    else:
                        parsed = str(parsed)

                if isinstance(parsed, str):
                    try:
                        parsed = json.loads(parsed)
                    except json.JSONDecodeError:
                        try:
                            parsed = ast.literal_eval(parsed)
                        except (ValueError, SyntaxError):
                            pass

                if isinstance(parsed, dict):
                    library_details = parsed
                    try:
                        save_library_status_snapshot(values, parsed)
                        save_status_ok = True
                    except Exception as exc:
                        save_status_error = f"Could not save status to MongoDB: {exc}"
                elif isinstance(parsed, list):
                    library_details_raw = json.dumps(parsed, indent=2, ensure_ascii=False)
                else:
                    library_details_raw = str(parsed)

            except Exception as exc:
                errors.append(f"Library API call failed: {exc}")

    return render(
        request,
        "slspstafftool/index.html",
        {
            "values": values,
            "errors": errors,
            "submitted": submitted,
            "library_details": library_details,
            "library_details_raw": library_details_raw,
            "save_status_ok": save_status_ok,
            "save_status_error": save_status_error,
        },
    )